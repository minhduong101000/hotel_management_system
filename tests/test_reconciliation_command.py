import json
from datetime import date
from decimal import Decimal

from extensions import db
from models import Booking, BookingService, Payment, Room, Service
from models.inventory_batch import InventoryBatch
from models.inventory_item import InventoryItem


APPLY_ARGS = [
    "reconcile-business-data",
    "--hotel-slug",
    "central",
    "--apply",
    "--confirm-apply",
    "--backup-acknowledged",
]


def _parse_report(result):
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def _seed_inventory_mismatch(hotel, *, quantity=10, batch_quantity=4):
    service = Service(hotel_id=hotel.id, name="Nước minibar", price=20000)
    db.session.add(service)
    db.session.flush()
    item = InventoryItem(
        hotel_id=hotel.id,
        code="NUOC",
        name="Nước suối",
        quantity=quantity,
        min_quantity=2,
        price=10000,
        service_id=service.id,
    )
    db.session.add(item)
    db.session.flush()
    db.session.add(
        InventoryBatch(
            hotel_id=hotel.id,
            inventory_item_id=item.id,
            batch_code="NUOC-001",
            received_at=date(2026, 7, 1),
            quantity_received=batch_quantity,
            quantity_available=batch_quantity,
            unit_cost=Decimal("10000"),
            status="active",
        )
    )
    return service, item


def test_reconciliation_dry_run_reports_only_target_tenant_without_mutation(
    app,
    seed_hotels,
):
    hotel_a, hotel_b, _, _, booking_room_a, booking_room_b = seed_hotels
    booking_a = booking_room_a.booking
    booking_b = booking_room_b.booking
    booking_a.total_amount = Decimal("999999")
    booking_a.status = "cancelled"
    booking_a.payment_status = "paid"
    booking_room_a.room.status = "occupied"
    booking_room_a.price_breakdown_snapshot = None
    booking_b.code = "TENANT-B-SECRET"
    booking_b.total_amount = Decimal("987654321")

    service, item = _seed_inventory_mismatch(hotel_a)
    db.session.flush()
    db.session.add(
        BookingService(
            hotel_id=hotel_a.id,
            booking_id=booking_a.id,
            room_id=booking_room_a.room_id,
            service_id=service.id,
            quantity=2,
            price_at_booking=20000,
        )
    )
    db.session.add(
        Payment(
            hotel_id=hotel_a.id,
            booking_id=booking_a.id,
            amount=Decimal("100000"),
            payment_type="room_payment",
        )
    )
    db.session.add(
        Payment(
            hotel_id=hotel_b.id,
            booking_id=booking_a.id,
            amount=Decimal("1"),
            payment_type="deposit",
        )
    )
    db.session.commit()

    result = app.test_cli_runner().invoke(
        args=[
            "reconcile-business-data",
            "--hotel-slug",
            hotel_a.slug,
        ]
    )
    report = _parse_report(result)
    rules = {issue["rule"] for issue in report["issues"]}

    assert report["mode"] == "dry-run"
    assert report["tenant"] == hotel_a.slug
    assert {
        "booking_total",
        "booking_state",
        "payment_operation",
        "inventory_total",
        "service_allocation",
        "price_snapshot",
        "room_occupancy",
        "tenant_link",
    }.issubset(rules)
    assert all("hotel_id" not in issue for issue in report["issues"])
    assert "TENANT-B-SECRET" not in result.output
    assert "987654321" not in result.output

    db.session.expire_all()
    assert booking_a.total_amount == Decimal("999999")
    assert booking_a.status == "cancelled"
    assert booking_room_a.room.status == "occupied"
    assert item.quantity == 10


def test_reconciliation_apply_requires_explicit_confirmation_and_backup(app):
    runner = app.test_cli_runner()

    missing_confirmation = runner.invoke(
        args=[
            "reconcile-business-data",
            "--hotel-slug",
            "central",
            "--apply",
        ]
    )
    missing_backup = runner.invoke(
        args=[
            "reconcile-business-data",
            "--hotel-slug",
            "central",
            "--apply",
            "--confirm-apply",
        ]
    )

    assert missing_confirmation.exit_code != 0
    assert "--confirm-apply" in missing_confirmation.output
    assert missing_backup.exit_code != 0
    assert "--backup-acknowledged" in missing_backup.output


def test_reconciliation_cli_output_is_safe_when_windows_redirects_stdout(
    app,
    seed_hotels,
):
    hotel, _, _, _, _, _ = seed_hotels
    runner = app.test_cli_runner()

    help_result = runner.invoke(args=["reconcile-business-data", "--help"])
    report_result = runner.invoke(
        args=[
            "reconcile-business-data",
            "--hotel-slug",
            hotel.slug,
        ]
    )

    assert help_result.exit_code == 0
    assert report_result.exit_code == 0
    help_result.output.encode("ascii")
    report_result.output.encode("ascii")


def test_reconciliation_apply_fixes_only_evidence_backed_rules_and_is_idempotent(
    app,
    seed_hotels,
):
    hotel, _, _, _, booking_room, _ = seed_hotels
    booking = booking_room.booking
    booking.status = "cancelled"
    booking.total_amount = Decimal("123456")
    booking_room.room.status = "occupied"
    _, item = _seed_inventory_mismatch(hotel)
    db.session.commit()
    booking_id = booking.id
    room_id = booking_room.room_id
    item_id = item.id
    db.session.remove()

    runner = app.test_cli_runner()
    first_report = _parse_report(runner.invoke(args=APPLY_ARGS))

    db.session.remove()
    refreshed_booking = db.session.get(Booking, booking_id)
    assert refreshed_booking.status == "confirmed"
    assert refreshed_booking.total_amount == Decimal("123456")
    assert db.session.get(Room, room_id).status == "available"
    assert db.session.get(InventoryItem, item_id).quantity == 4
    assert first_report["summary"]["applied_count"] == 3
    booking_total_issue = next(
        issue
        for issue in first_report["issues"]
        if issue["rule"] == "booking_total"
    )
    assert booking_total_issue["requires_manual_review"] is True
    assert booking_total_issue["applied"] is False

    db.session.remove()
    second_report = _parse_report(runner.invoke(args=APPLY_ARGS))
    assert second_report["summary"]["applied_count"] == 0
    assert any(
        issue["rule"] == "booking_total"
        for issue in second_report["issues"]
    )


def test_reconciliation_apply_rolls_back_tenant_when_a_rule_fails(
    app,
    seed_hotels,
    monkeypatch,
):
    from services import reconciliation_service

    hotel, _, _, _, booking_room, _ = seed_hotels
    booking = booking_room.booking
    booking.status = "cancelled"
    db.session.commit()
    booking_id = booking.id
    db.session.remove()

    def mutate_rule(hotel_id, *, apply):
        target = booking.__class__.query.filter_by(
            hotel_id=hotel_id,
            id=booking.id,
        ).one()
        if apply:
            target.status = "confirmed"
        return [
            reconciliation_service.issue(
                rule="test_mutation",
                entity_type="booking",
                entity_id=target.id,
                current="cancelled",
                expected="confirmed",
                can_apply=True,
                applied=apply,
            )
        ]

    def failing_rule(_hotel_id, *, apply):
        if apply:
            raise RuntimeError("forced reconciliation failure")
        return []

    monkeypatch.setattr(
        reconciliation_service,
        "RECONCILIATION_RULES",
        (mutate_rule, failing_rule),
    )

    result = app.test_cli_runner().invoke(args=APPLY_ARGS)

    assert result.exit_code != 0
    assert "rollback" in result.output
    db.session.remove()
    assert db.session.get(Booking, booking_id).status == "cancelled"
