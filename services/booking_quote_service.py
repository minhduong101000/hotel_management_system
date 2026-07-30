from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json

from models.booking_room import BookingRoom
from models.booking_service import BookingService
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
    check_in = (
        booking_room.check_in_actual
        or booking_room.check_in_expected
        or checkout_at
    )
    room_quote = _room_quote(
        booking_room.room,
        check_in,
        checkout_at,
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


def is_expired(quote, now=None):
    now = (now or datetime.now()).replace(microsecond=0)
    return now > datetime.fromisoformat(quote["expires_at"])
