from decimal import Decimal, InvalidOperation


class RoomConfigurationValidationError(Exception):
    def __init__(self, errors):
        super().__init__('Room configuration validation failed')
        self.errors = errors


def _require_json_object(data):
    if not isinstance(data, dict):
        raise RoomConfigurationValidationError(
            {'request': 'Dữ liệu gửi lên phải là một đối tượng JSON.'}
        )


def _required_text(data, field, maximum_length, errors):
    value = data.get(field)
    if not isinstance(value, str):
        errors[field] = 'Trường này là bắt buộc.'
        return None

    value = value.strip()
    if not value:
        errors[field] = 'Trường này là bắt buộc.'
    elif len(value) > maximum_length:
        errors[field] = f'Tối đa {maximum_length} ký tự.'

    return value


def _required_positive_amount(data, field, errors):
    raw_value = data.get(field)
    if isinstance(raw_value, bool):
        errors[field] = 'Giá phải là số nguyên dương.'
        return None

    try:
        value = Decimal(str(raw_value))
    except (InvalidOperation, ValueError):
        errors[field] = 'Giá phải là số nguyên dương.'
        return None

    if not value.is_finite() or value <= 0 or value != value.to_integral_value():
        errors[field] = 'Giá phải là số nguyên dương.'
        return None

    return int(value)


def _required_positive_integer(data, field, errors):
    raw_value = data.get(field)
    if isinstance(raw_value, bool):
        errors[field] = 'Số giờ phải là số nguyên dương.'
        return None

    try:
        value = Decimal(str(raw_value))
    except (InvalidOperation, ValueError):
        errors[field] = 'Số giờ phải là số nguyên dương.'
        return None

    if not value.is_finite() or value <= 0 or value != value.to_integral_value():
        errors[field] = 'Số giờ phải là số nguyên dương.'
        return None

    return int(value)


def _validated_rates(data, errors):
    return {
        'price_per_night': _required_positive_amount(data, 'price_per_night', errors),
        'price_initial_block': _required_positive_amount(
            data, 'price_initial_block', errors
        ),
        'initial_hours': _required_positive_integer(data, 'initial_hours', errors),
        'price_next_hour': _required_positive_amount(data, 'price_next_hour', errors),
    }


def _validated_room_structure(data, errors):
    return {
        'room_number': _required_text(data, 'room_number', 10, errors),
        'room_type': _required_text(data, 'room_type', 20, errors),
    }


def _raise_if_invalid(errors):
    if errors:
        raise RoomConfigurationValidationError(errors)


def validate_room_create_payload(data):
    _require_json_object(data)

    errors = {}
    values = _validated_room_structure(data, errors)
    values.update(_validated_rates(data, errors))

    maintenance = data.get('maintenance', False)
    if not isinstance(maintenance, bool):
        errors['maintenance'] = 'Trạng thái bảo trì phải là true hoặc false.'
    else:
        values['maintenance'] = maintenance

    _raise_if_invalid(errors)

    return values


def validate_room_update_payload(data):
    _require_json_object(data)

    errors = {}
    values = _validated_room_structure(data, errors)
    values.update(_validated_rates(data, errors))
    _raise_if_invalid(errors)
    return values


def validate_room_maintenance_payload(data):
    _require_json_object(data)
    maintenance = data.get('maintenance')
    if not isinstance(maintenance, bool):
        raise RoomConfigurationValidationError({
            'maintenance': 'Trạng thái bảo trì phải là true hoặc false.',
        })
    return maintenance


def _value_with_legacy_alias(data, canonical_key, legacy_key):
    if canonical_key in data:
        return data[canonical_key]
    return data.get(legacy_key)


def validate_default_rate_update_payload(data, current_initial_hours):
    _require_json_object(data)

    normalized = {
        'price_per_night': _value_with_legacy_alias(
            data, 'price_per_night', 'price_daily'
        ),
        'price_initial_block': _value_with_legacy_alias(
            data, 'price_initial_block', 'price_initial'
        ),
        'initial_hours': data.get('initial_hours', current_initial_hours),
        'price_next_hour': _value_with_legacy_alias(
            data, 'price_next_hour', 'price_next'
        ),
    }
    errors = {}
    values = _validated_rates(normalized, errors)
    _raise_if_invalid(errors)
    return values


def serialize_room_settings(room, active_booking_count=0):
    return {
        'id': room.id,
        'room_number': room.room_number,
        'room_type': room.room_type,
        'price_per_night': float(room.price_per_night or 0),
        'price_initial_block': float(room.price_initial_block or 0),
        'initial_hours': int(room.initial_hours or 0),
        'price_next_hour': float(room.price_next_hour or 0),
        'status': room.status,
        'clean_status': room.clean_status,
        'active_booking_count': int(active_booking_count or 0),
    }


def room_audit_snapshot(room):
    return {
        'room_number': room.room_number,
        'room_type': room.room_type,
        'price_per_night': float(room.price_per_night or 0),
        'price_initial_block': float(room.price_initial_block or 0),
        'initial_hours': int(room.initial_hours or 0),
        'price_next_hour': float(room.price_next_hour or 0),
        'status': room.status,
        'clean_status': room.clean_status,
    }
