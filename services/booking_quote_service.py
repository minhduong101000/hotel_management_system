from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json

from models.booking_room import BookingRoom
from models.booking_service import BookingService
from services import time_service
from services.pricing_service import calculate_complex_hotel_bill


QUOTE_VERSION = "booking-quote-v1"
QUOTE_TTL = timedelta(minutes=5)
MONEY_QUANTUM = Decimal("0.01")
TAX_RATE = Decimal("0.08")


def money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(
        MONEY_QUANTUM,
        rounding=ROUND_HALF_UP,
    )


def money_string(value) -> str:
    return format(money(value), ".2f")


def _fingerprint(payload) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _finalize_quote(payload):
    quote = dict(payload)
    quote["fingerprint"] = _fingerprint(quote)
    return quote


def _room_quote(room, check_in, check_out, rental_type, **bill_options):
    room_total, breakdown = calculate_complex_hotel_bill(
        check_in,
        check_out,
        room,
        rental_type=rental_type,
        **bill_options,
    )
    return {
        "room_id": room.id,
        "room_number": room.room_number,
        "rental_type": rental_type,
        "amount": money(room_total),
        "lines": [
            {
                "label": line.get("label", ""),
                "detail": line.get("detail", ""),
                "source": line.get("source") or "calculated",
                "amount": money_string(line.get("amount", 0)),
            }
            for line in breakdown
        ],
    }


def build_new_booking_quote(
    rooms,
    *,
    check_in: datetime,
    check_out: datetime,
    rental_type: str = "daily",
    include_tax: bool = False,
):
    room_quotes = [
        _room_quote(room, check_in, check_out, rental_type)
        for room in rooms
    ]
    room_subtotal = sum(
        (room_quote["amount"] for room_quote in room_quotes),
        Decimal("0"),
    )
    tax = money(room_subtotal * TAX_RATE) if include_tax else Decimal("0")
    total = money(room_subtotal + tax)

    payload = {
        "version": QUOTE_VERSION,
        "kind": "new_booking",
        "currency": "VND",
        "check_in": check_in.replace(microsecond=0).isoformat(),
        "check_out": check_out.replace(microsecond=0).isoformat(),
        "include_tax": bool(include_tax),
        "room_lines": [
            {
                **{
                    key: value
                    for key, value in room_quote.items()
                    if key != "amount"
                },
                "amount": money_string(room_quote["amount"]),
            }
            for room_quote in room_quotes
        ],
        "service_lines": [],
        "room_subtotal": money_string(room_subtotal),
        "service_subtotal": "0.00",
        "tax_rate": money_string(TAX_RATE),
        "tax": money_string(tax),
        "deposit": "0.00",
        "total": money_string(total),
        "balance": money_string(total),
        "deposit_options": {
            "suggested_50": money_string(total * Decimal("0.50")),
            "maximum_100": money_string(total),
        },
    }
    return _finalize_quote(payload)


def validate_deposit(quote, deposit, tolerance=Decimal("1.00")):
    deposit_amount = money(deposit)
    options = quote["deposit_options"]
    return any(
        abs(deposit_amount - money(candidate)) <= tolerance
        for candidate in (
            options["suggested_50"],
            options["maximum_100"],
        )
    )


def build_checkout_quote(
    booking_room,
    *,
    checkout_at: datetime,
    include_tax: bool,
):
    checkout_at = checkout_at.replace(microsecond=0)

    # pricing_service là hàm THUẦN giờ nghiệp vụ: quy đổi mọi mốc UTC tại đây.
    # Lưu ý: checkout_at trả ra trong quote phải GIỮ NGUYÊN UTC vì nó dùng cho
    # quote_fingerprint và được ghi vào check_out_actual.
    if booking_room.check_in_actual:
        check_in_business = time_service.to_business_naive(booking_room.check_in_actual)
    else:
        check_in_business = booking_room.check_in_expected or time_service.to_business_naive(checkout_at)
    checkout_business = time_service.to_business_naive(checkout_at)

    room_quote = _room_quote(
        booking_room.room,
        check_in_business,
        checkout_business,
        booking_room.rental_type,
        expected_check_in=booking_room.check_in_expected,
        expected_check_out=booking_room.check_out_expected,
        price_breakdown_snapshot=booking_room.price_breakdown_snapshot,
        hourly_price_snapshot=booking_room.hourly_price_snapshot,
    )

    service_rows = (
        BookingService.query.filter_by(
            hotel_id=booking_room.hotel_id,
            booking_id=booking_room.booking_id,
            room_id=booking_room.room_id,
        )
        .order_by(BookingService.id.asc())
        .all()
    )
    service_lines = []
    service_subtotal = Decimal("0")
    for row in service_rows:
        quantity = int(row.quantity or 0)
        unit_price = money(
            row.price_at_booking
            or (row.service.price if row.service else 0)
        )
        line_amount = money(unit_price * quantity)
        service_subtotal += line_amount
        service_lines.append({
            "service_id": row.service_id,
            "name": row.service.name if row.service else "Dịch vụ",
            "quantity": quantity,
            "unit_price": money_string(unit_price),
            "amount": money_string(line_amount),
        })

    room_subtotal = room_quote["amount"]
    subtotal = money(room_subtotal + service_subtotal)
    tax = money(subtotal * TAX_RATE) if include_tax else Decimal("0")
    total = money(subtotal + tax)

    other_active_room = (
        BookingRoom.query.filter(
            BookingRoom.hotel_id == booking_room.hotel_id,
            BookingRoom.booking_id == booking_room.booking_id,
            BookingRoom.id != booking_room.id,
            BookingRoom.status.in_(["booked", "checked_in"]),
        )
        .first()
    )
    apply_deposit = other_active_room is None
    deposit = (
        money(booking_room.booking.prepaid_amount)
        if apply_deposit and booking_room.booking
        else Decimal("0")
    )
    balance = money(total - deposit)

    payload = {
        "version": QUOTE_VERSION,
        "kind": "checkout",
        "currency": "VND",
        "hotel_id": booking_room.hotel_id,
        "booking_id": booking_room.booking_id,
        "booking_room_id": booking_room.id,
        "room_number": booking_room.room.room_number,
        "checkout_at": checkout_at.isoformat(),
        "expires_at": (checkout_at + QUOTE_TTL).isoformat(),
        "include_tax": bool(include_tax),
        "room_lines": room_quote["lines"],
        "service_lines": service_lines,
        "room_subtotal": money_string(room_subtotal),
        "service_subtotal": money_string(service_subtotal),
        "subtotal": money_string(subtotal),
        "tax_rate": money_string(TAX_RATE),
        "tax": money_string(tax),
        "apply_deposit": apply_deposit,
        "deposit": money_string(deposit),
        "total": money_string(total),
        "balance": money_string(balance),
    }
    return _finalize_quote(payload)


def build_group_checkout_quote(
    booking,
    *,
    checkout_at: datetime,
    include_tax: bool,
):
    """Tạo một báo giá checkout đoàn từ trạng thái hiện tại của toàn booking."""
    checkout_at = checkout_at.replace(microsecond=0)
    state_groups = {
        "checked_in": [],
        "booked": [],
        "checked_out": [],
        "cancelled": [],
    }
    room_quotes = []
    room_subtotal = Decimal("0")
    service_subtotal = Decimal("0")
    tax = Decimal("0")
    settlement_total = Decimal("0")
    finalized_total = Decimal("0")

    for booking_room in sorted(booking.rooms, key=lambda row: row.id):
        room_number = (
            booking_room.room.room_number
            if booking_room.room
            else str(booking_room.room_id)
        )
        status = booking_room.status or "unknown"
        state_groups.setdefault(status, []).append(room_number)

        if status == "checked_in":
            room_quote = build_checkout_quote(
                booking_room,
                checkout_at=checkout_at,
                include_tax=include_tax,
            )
            current_room = money(room_quote["room_subtotal"])
            current_service = money(room_quote["service_subtotal"])
            current_tax = money(room_quote["tax"])
            current_total = money(room_quote["total"])
            room_subtotal += current_room
            service_subtotal += current_service
            tax += current_tax
            settlement_total += current_total
            room_quotes.append({
                "booking_room_id": booking_room.id,
                "room_id": booking_room.room_id,
                "room_number": room_number,
                "status": status,
                "include_in_settlement": True,
                "room_subtotal": money_string(current_room),
                "service_subtotal": money_string(current_service),
                "tax": money_string(current_tax),
                "total": money_string(current_total),
                "room_lines": room_quote["room_lines"],
                "service_lines": room_quote["service_lines"],
            })
            continue

        current_total = (
            money(booking_room.final_amount)
            if status in ("checked_out", "cancelled")
            else Decimal("0")
        )
        if status in ("checked_out", "cancelled"):
            finalized_total += current_total
        room_quotes.append({
            "booking_room_id": booking_room.id,
            "room_id": booking_room.room_id,
            "room_number": room_number,
            "status": status,
            "include_in_settlement": False,
            "room_subtotal": money_string(current_total),
            "service_subtotal": "0.00",
            "tax": "0.00",
            "total": money_string(current_total),
            "room_lines": [],
            "service_lines": [],
        })

    room_subtotal = money(room_subtotal)
    service_subtotal = money(service_subtotal)
    tax = money(tax)
    settlement_subtotal = money(room_subtotal + service_subtotal)
    settlement_total = money(settlement_total)
    finalized_total = money(finalized_total)
    booking_total = money(finalized_total + settlement_total)
    deposit = money(booking.prepaid_amount)
    balance = money(settlement_total - deposit)

    payload = {
        "version": QUOTE_VERSION,
        "kind": "group_checkout",
        "currency": "VND",
        "hotel_id": booking.hotel_id,
        "booking_id": booking.id,
        "checkout_at": checkout_at.isoformat(),
        "expires_at": (checkout_at + QUOTE_TTL).isoformat(),
        "include_tax": bool(include_tax),
        "rooms": room_quotes,
        "state_groups": state_groups,
        "room_subtotal": money_string(room_subtotal),
        "service_subtotal": money_string(service_subtotal),
        "settlement_subtotal": money_string(settlement_subtotal),
        "tax_rate": money_string(TAX_RATE),
        "tax": money_string(tax),
        "settlement_total": money_string(settlement_total),
        "finalized_total": money_string(finalized_total),
        "booking_total": money_string(booking_total),
        "deposit": money_string(deposit),
        "balance": money_string(balance),
    }
    return _finalize_quote(payload)


def is_expired(quote, now=None):
    now = (now or time_service.utc_now_naive()).replace(microsecond=0)
    return now > datetime.fromisoformat(quote["expires_at"])
