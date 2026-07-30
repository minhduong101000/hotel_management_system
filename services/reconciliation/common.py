from decimal import Decimal


def value(value):
    if isinstance(value, Decimal):
        return format(value, ".2f")
    return value


def money(value):
    return Decimal(str(value or 0))


def issue(
    *,
    rule,
    entity_type,
    entity_id,
    current,
    expected,
    can_apply=False,
    applied=False,
    note=None,
):
    result = {
        "rule": rule,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "current": value(current),
        "expected": value(expected),
        "can_apply": bool(can_apply),
        "applied": bool(applied),
        "requires_manual_review": not bool(can_apply),
    }
    if note:
        result["note"] = note
    return result
