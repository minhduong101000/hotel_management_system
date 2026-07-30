from services.reconciliation import (
    issue,
    reconcile_booking_aggregates,
    reconcile_inventory_totals,
    reconcile_payment_operations,
    reconcile_room_number_constraint,
    reconcile_room_occupancy,
    reconcile_service_allocations,
    reconcile_tenant_links,
)


RECONCILIATION_RULES = (
    reconcile_booking_aggregates,
    reconcile_payment_operations,
    reconcile_room_occupancy,
    reconcile_inventory_totals,
    reconcile_service_allocations,
    reconcile_tenant_links,
    reconcile_room_number_constraint,
)


def run_reconciliation(*, hotel_id, apply=False):
    issues = []
    for rule in RECONCILIATION_RULES:
        issues.extend(rule(hotel_id, apply=apply))
    issues.sort(
        key=lambda row: (
            row["rule"],
            row["entity_type"],
            row["entity_id"] if row["entity_id"] is not None else -1,
        )
    )
    return {
        "issues": issues,
        "summary": {
            "issue_count": len(issues),
            "applied_count": sum(1 for row in issues if row["applied"]),
            "manual_review_count": sum(
                1 for row in issues if row["requires_manual_review"]
            ),
        },
    }
