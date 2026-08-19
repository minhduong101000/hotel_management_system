from datetime import datetime, time, timedelta
import math
from sqlalchemy import and_, or_

# Import model PriceRule
# Lưu ý: Cần chắc chắn đường dẫn import đúng với cấu trúc thư mục của bạn
from models.price_rule import PriceRule 


def get_billable_night_dates(check_in: datetime, check_out: datetime):
    """Return business dates for each nightly charge in [check_in, check_out)."""
    start_date = check_in.date()
    end_date = check_out.date()
    nights = max(1, (end_date - start_date).days)
    return [start_date + timedelta(days=offset) for offset in range(nights)]


def get_nightly_price_breakdown(room, check_in: datetime, check_out: datetime):
    return [
        {'business_date': night_date, 'amount': get_effective_room_prices(room, datetime.combine(night_date, time(14, 0)))['p_night']}
        for night_date in get_billable_night_dates(check_in, check_out)
    ]


def extend_nightly_price_snapshot(
    price_breakdown_snapshot,
    check_in: datetime,
    check_out: datetime,
):
    """Extend a committed nightly snapshot using its last nightly amount."""
    if not price_breakdown_snapshot:
        return []

    snapshot_by_date = {
        str(line.get('business_date'))[:10]: {
            'business_date': str(line.get('business_date'))[:10],
            'amount': float(line.get('amount', 0)),
            'source': line.get('source') or 'snapshot',
        }
        for line in price_breakdown_snapshot
    }
    ordered_snapshot = sorted(
        snapshot_by_date.values(),
        key=lambda line: line['business_date'],
    )
    last_snapshot = ordered_snapshot[-1]
    last_snapshot_date = last_snapshot['business_date']
    last_snapshot_amount = last_snapshot['amount']

    result = []
    for business_date in get_billable_night_dates(check_in, check_out):
        date_key = business_date.isoformat()
        if date_key in snapshot_by_date:
            result.append(snapshot_by_date[date_key].copy())
        elif date_key > last_snapshot_date:
            result.append({
                'business_date': date_key,
                'amount': last_snapshot_amount,
                'source': 'overstay_extension',
            })
    return result

# =======================================================
# 1. HÀM LẤY GIÁ (CÓ CHECK RULE LỄ TẾT)
# =======================================================
def _base_room_prices(room):
    base_price_night = float(getattr(room, 'price_per_night', 0))
    base_price_initial = float(getattr(room, 'price_initial_block', 0)) or (base_price_night / 4)
    base_price_next = float(getattr(room, 'price_next_hour', 0)) or (base_price_night / 10)
    raw_initial_hours = getattr(room, 'initial_hours', 2)
    try:
        initial_hours_val = int(raw_initial_hours)
    except (TypeError, ValueError):
        initial_hours_val = 2
    if initial_hours_val < 1:
        initial_hours_val = 2

    return {
        'p_initial': base_price_initial,
        'p_next': base_price_next,
        'p_night': base_price_night,
        'initial_hours': initial_hours_val,
        'is_special': False,
        'rule_name': 'Giá niêm yết'
    }


def _apply_effective_rule(room, check_date, candidate_rules):
    prices = _base_room_prices(room)
    current_weekday = str(check_date.weekday())
    selected_rule = next(
        (
            rule
            for rule in candidate_rules
            if not rule.days_of_week
            or current_weekday in rule.days_of_week.split(',')
        ),
        None,
    )
    if selected_rule:
        if selected_rule.price_daily > 0:
            prices['p_night'] = float(selected_rule.price_daily)
        prices['is_special'] = True
        prices['rule_name'] = selected_rule.name
    return prices


def _effective_rule_query(hotel_id, room_types, check_date):
    return PriceRule.query.filter(
        PriceRule.hotel_id == hotel_id,
        PriceRule.room_type.in_(room_types),
        PriceRule.is_active.is_(True),
        or_(PriceRule.start_date.is_(None), PriceRule.start_date <= check_date.date()),
        or_(PriceRule.end_date.is_(None), PriceRule.end_date >= check_date.date()),
    ).order_by(PriceRule.priority.desc())


def get_effective_room_prices(room, check_date=None):
    """Return effective prices for one room."""
    check_date = check_date or datetime.now()
    try:
        candidate_rules = _effective_rule_query(
            room.hotel_id,
            [room.room_type],
            check_date,
        ).all()
    except RuntimeError:
        candidate_rules = []
    return _apply_effective_rule(room, check_date, candidate_rules)


def get_effective_room_prices_bulk(rooms, check_date=None):
    """Load applicable rules once and calculate prices for all supplied rooms."""
    rooms = list(rooms)
    if not rooms:
        return {}

    check_date = check_date or datetime.now()
    hotel_id = rooms[0].hotel_id
    room_types = sorted({room.room_type for room in rooms})
    candidate_rules = _effective_rule_query(
        hotel_id,
        room_types,
        check_date,
    ).all()
    rules_by_type = {}
    for rule in candidate_rules:
        rules_by_type.setdefault(rule.room_type, []).append(rule)

    return {
        room.id: _apply_effective_rule(
            room,
            check_date,
            rules_by_type.get(room.room_type, []),
        )
        for room in rooms
    }

# =======================================================
# 2. HELPER: TÍNH % PHỤ THU (SỚM/MUỘN)
# =======================================================
def get_surcharge_ratio(hours_val):
    """Trả về tỉ lệ phụ thu dựa trên số giờ chênh lệch."""
    h = float(hours_val)
    if h <= 1: # Grace period < 1h -> Miễn phí
        return 0.0, "Miễn phí"
    elif 1 < h <= 4:
        return 0.3, "30%"
    elif 4 < h <= 6:
        return 0.5, "50%"
    else:
        return 1.0, "100%"

# =======================================================
# 3. HELPER: TÍNH TIỀN GIỜ (THEO BLOCK)
# =======================================================
def calculate_raw_hourly_fee(check_in, check_out, price_config):
    """
    Tính tiền giờ thuần túy dựa trên config giá.
    Return: (amount, duration_hours, description)
    """
    duration = check_out - check_in
    minutes = duration.total_seconds() / 60
    
    p_initial = price_config['p_initial']
    p_next = price_config['p_next']
    h_initial = price_config['initial_hours']
    
    GRACE_MINUTES = 10 # Cho phép lố 10 phút không tính tiền
    
    # Tính số giờ làm tròn (Round up)
    # Ví dụ: Block đầu 1h. Khách ở 1h05p -> Vẫn tính 1h. Khách ở 1h15p -> Tính 2h.
    
    if minutes <= (h_initial * 60) + GRACE_MINUTES:
        billable_hours = h_initial
    else:
        # Trừ thời gian ân hạn rồi mới làm tròn lên
        extra_minutes = minutes - GRACE_MINUTES
        billable_hours = math.ceil(extra_minutes / 60)
        
    billable_hours = max(h_initial, billable_hours)

    # Tính tiền
    if billable_hours <= h_initial:
        total = p_initial
        desc = f"{billable_hours} giờ đầu"
    else:
        extra_hours = billable_hours - h_initial
        total = p_initial + (extra_hours * p_next)
        desc = f"{h_initial}h đầu + {extra_hours}h tiếp theo"

    return total, billable_hours, desc


def apply_hourly_price_snapshot(prices, hourly_price_snapshot):
    """Use the hourly rates committed at booking time when they are available."""
    if not hourly_price_snapshot:
        return prices

    try:
        snapshot_prices = {
            'initial_hours': int(hourly_price_snapshot['initial_hours']),
            'p_initial': float(hourly_price_snapshot['price_initial']),
            'p_next': float(hourly_price_snapshot['price_next']),
            'p_night': float(hourly_price_snapshot['price_night']),
        }
    except (KeyError, TypeError, ValueError):
        return prices

    if snapshot_prices['initial_hours'] < 1 or any(value < 0 for value in snapshot_prices.values() if isinstance(value, float)):
        return prices

    committed = prices.copy()
    committed.update(snapshot_prices)
    committed['is_special'] = False
    committed['rule_name'] = 'Giá đã chốt'
    return committed

# =======================================================
# 4. HÀM LOGIC CHÍNH (MAIN FUNCTION) - ĐÃ SỬA
# =======================================================
def calculate_complex_hotel_bill(check_in, check_out, room, rental_type='hourly', 
                                 expected_check_in=None, expected_check_out=None,
                                 price_breakdown_snapshot=None,
                                 hourly_price_snapshot=None):
    """
    Hàm tính tiền chuẩn xác (Fix lỗi phụ thu hàng trăm giờ):
    1. Base Fee (Tiền phòng): Tính số ĐÊM dựa trên khoảng ngày rộng nhất (để thu đủ nếu ở lố ngày).
    2. Surcharge (Phụ thu): CHỈ tính số GIỜ lố trong ngày check-in/check-out thực tế.

    HỢP ĐỒNG THỜI GIAN: mọi tham số datetime (check_in, check_out,
    expected_check_in, expected_check_out) phải là GIỜ NGHIỆP VỤ VN dạng naive.
    Người gọi chịu trách nhiệm quy đổi — xem build_checkout_quote.
    """
    
    # Cấu hình giờ chuẩn của khách sạn
    STD_IN_HOUR = 14  # 14:00
    STD_OUT_HOUR = 12 # 12:00

    prices = get_effective_room_prices(room, check_in)
    if rental_type == 'hourly':
        prices = apply_hourly_price_snapshot(prices, hourly_price_snapshot)
    rule_tag = f" ({prices['rule_name']})" if prices['is_special'] else ""
    
    total_fee = 0.0
    breakdown = []
    
    use_daily_rule = (rental_type == 'daily')

    # ====================================================
    # PHẦN 1: TÍNH TIỀN PHÒNG CƠ BẢN (SỐ ĐÊM/GIỜ)
    # ====================================================
    
    # Tính MỐC NGÀY để tính tiền phòng (Lấy khoảng rộng nhất)
    # Khách đến trước ngày book -> Tính từ ngày đến. Khách đến muộn -> Tính từ ngày book.
    bill_start_date = min(check_in.date(), expected_check_in.date()) if expected_check_in else check_in.date()
    
    # Khách về sau ngày book -> Tính đến ngày về. Khách về sớm -> Tính đến ngày book.
    bill_end_date = max(check_out.date(), expected_check_out.date()) if expected_check_out else check_out.date()

    if rental_type == 'hourly':
        # Thuê giờ: luôn tính theo thời gian ở thực tế.
        raw_fee, billed_hours, note = calculate_raw_hourly_fee(check_in, check_out, prices)
        
        if raw_fee > prices['p_night']:
            use_daily_rule = True
        else:
            total_fee = raw_fee
            breakdown.append({
                "label": f"Tiền giờ{rule_tag}",
                "detail": note,
                "amount": total_fee
            })

    if use_daily_rule:
        if rental_type == 'hourly':
            breakdown.append({
                "label": "Tự động chuyển đổi",
                "detail": "Tiền giờ > Giá đêm. Chuyển sang tính theo đêm.",
                "amount": 0
            })

        # LOGIC MỚI: Tính số đêm chính xác dựa trên khoảng ngày
        if price_breakdown_snapshot:
            nightly_breakdown = extend_nightly_price_snapshot(
                price_breakdown_snapshot,
                datetime.combine(bill_start_date, time(14, 0)),
                datetime.combine(bill_end_date, time(12, 0)),
            )
        elif rental_type == 'hourly' and hourly_price_snapshot:
            nightly_breakdown = [
                {'business_date': night_date, 'amount': prices['p_night']}
                for night_date in get_billable_night_dates(
                    datetime.combine(bill_start_date, time(14, 0)),
                    datetime.combine(bill_end_date, time(12, 0)),
                )
            ]
        else:
            nightly_breakdown = get_nightly_price_breakdown(
                room, datetime.combine(bill_start_date, time(14, 0)), datetime.combine(bill_end_date, time(12, 0)))
        nights = len(nightly_breakdown)
        base_fee = sum(line['amount'] for line in nightly_breakdown)
        total_fee += base_fee
        
        breakdown.append({
            "label": f"Tiền phòng{rule_tag}",
            "detail": f"{nights} đêm (Từ {bill_start_date.strftime('%d/%m')} đến {bill_end_date.strftime('%d/%m')})",
            "amount": base_fee
        })
        for line in nightly_breakdown:
            line_source = line.get('source')
            breakdown.append({
                "label": f"Giá đêm {line['business_date'].strftime('%d/%m') if hasattr(line['business_date'], 'strftime') else line['business_date']}",
                "detail": (
                    "Nối dài theo giá snapshot đêm cuối"
                    if line_source == 'overstay_extension'
                    else "Giá đã chốt cho đêm này"
                    if line_source == 'snapshot'
                    else "Giá theo rule hiệu lực của đêm này"
                ),
                "amount": line['amount'],
                "source": line_source or "effective_price",
            })

        # ====================================================
        # PHẦN 2: TÍNH PHỤ THU (CHỈ TÍNH GIỜ TRONG NGÀY)
        # ====================================================
        total_extra_hours = 0.0
        extra_details = [] 

        # 1. CHECK-IN SỚM:
        early_h = 0
        if expected_check_in:
            if check_in.date() == expected_check_in.date():
                # Đến cùng ngày nhưng sớm hơn giờ book
                if check_in < expected_check_in:
                    early_h = (expected_check_in - check_in).total_seconds() / 3600.0
            elif check_in.date() < expected_check_in.date():
                # Đến trước cả ngày (Đã bị cộng thành 1 đêm ở trên)
                # Chỉ soi xem ngày đến đó có sớm hơn 14:00 không
                std_in_time = datetime.combine(check_in.date(), time(STD_IN_HOUR, 0))
                if check_in < std_in_time:
                    early_h = (std_in_time - check_in).total_seconds() / 3600.0

        if early_h > 0.2:
            total_extra_hours += early_h
            extra_details.append(f"Sớm {early_h:.1f}h")

        # 2. CHECK-OUT MUỘN:
        late_h = 0
        if expected_check_out:
            if check_out.date() <= expected_check_out.date():
                # Về đúng ngày hoặc về sớm (Đã thu đủ tiền đêm) -> Chỉ phạt nếu muộn hơn giờ book
                if check_out > expected_check_out:
                    late_h = (check_out - expected_check_out).total_seconds() / 3600.0
            else:
                # Về lố sang ngày hôm sau (Đã bị cộng thành các đêm ở trên)
                # Chỉ soi xem cái ngày đi đó có muộn hơn 12:00 trưa không
                std_out_time = datetime.combine(check_out.date(), time(STD_OUT_HOUR, 0))
                if check_out > std_out_time:
                    late_h = (check_out - std_out_time).total_seconds() / 3600.0

        if late_h > 0.2:
            total_extra_hours += late_h
            extra_details.append(f"Muộn {late_h:.1f}h")

        # 3. TỔNG HỢP PHỤ THU:
        if total_extra_hours > 0:
            ratio, r_note = get_surcharge_ratio(total_extra_hours)
            if ratio > 0:
                surcharge = prices['p_night'] * ratio
                total_fee += surcharge
                breakdown.append({
                    "label": "Phụ thu phát sinh",
                    "detail": f"Tổng {total_extra_hours:.1f}h ({', '.join(extra_details)})",
                    "amount": surcharge
                })
            else:
                 breakdown.append({
                    "label": "Phụ thu phát sinh",
                    "detail": f"Tổng {total_extra_hours:.1f}h (Miễn phí dưới 1h)",
                    "amount": 0
                })

    return total_fee, breakdown
