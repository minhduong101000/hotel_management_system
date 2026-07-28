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

# =======================================================
# 1. HÀM LẤY GIÁ (CÓ CHECK RULE LỄ TẾT)
# =======================================================
def get_effective_room_prices(room, check_date=None):
    """
    Lấy giá phòng thực tế tại thời điểm check_date.
    Logic: 
      - Giá giờ: LUÔN LẤY GỐC TỪ ROOM (PriceRule không can thiệp).
      - Giá ngày: Ưu tiên PriceRule (Lễ/Tết) > Giá niêm yết (Room).
    """
    if check_date is None:
        check_date = datetime.now()

    # --- A. Lấy giá gốc từ Room Settings ---
    # Sử dụng getattr để an toàn nếu model Room chưa cập nhật kịp attribute
    base_price_night = float(getattr(room, 'price_per_night', 0))
    
    # Giá giờ: Block đầu (VD: 2h đầu) và Block tiếp theo (mỗi giờ thêm)
    # Nếu DB không có cột này, tạm tính theo công thức mặc định
    base_price_initial = float(getattr(room, 'price_initial_block', 0)) or (base_price_night / 4)
    base_price_next = float(getattr(room, 'price_next_hour', 0)) or (base_price_night / 10)
    # Mặc định block đầu là 2 giờ nếu dữ liệu phòng thiếu/sai.
    raw_initial_hours = getattr(room, 'initial_hours', 2)
    try:
        initial_hours_val = int(raw_initial_hours)
    except (TypeError, ValueError):
        initial_hours_val = 2
    if initial_hours_val < 1:
        initial_hours_val = 2

    prices = {
        'p_initial': base_price_initial, # Giá block đầu
        'p_next': base_price_next,       # Giá các giờ sau
        'p_night': base_price_night,     # Giá ngày (đêm)
        'initial_hours': initial_hours_val,
        'is_special': False,
        'rule_name': 'Giá niêm yết'
    }

    # --- B. Tìm Rule áp dụng (Lễ, Tết, Mùa vụ) ---
    check_date_obj = check_date.date()
    
    # Tìm các rule đang active và thỏa mãn ngày
    try:
        candidate_rules = PriceRule.query.filter(
            and_(
                PriceRule.hotel_id == room.hotel_id,
                PriceRule.room_type == room.room_type,
                PriceRule.is_active == True,
                # Kiểm tra ngày nằm trong khoảng hiệu lực (Start -> End)
                or_(PriceRule.start_date.is_(None), PriceRule.start_date <= check_date_obj),
                or_(PriceRule.end_date.is_(None), PriceRule.end_date >= check_date_obj)
            )
        ).order_by(PriceRule.priority.desc()).all()
    except RuntimeError:
        # Cho phép chạy test/script ngoài Flask app context: bỏ qua rule đặc biệt.
        candidate_rules = []

    # --- C. Lọc rule theo Thứ trong tuần (Weekdays) ---
    selected_rule = None
    current_weekday = str(check_date.weekday()) # 0=Mon, 6=Sun

    for rule in candidate_rules:
        # 1. Nếu rule không quy định thứ (NULL hoặc rỗng) -> Áp dụng cả tuần
        if not rule.days_of_week:
            selected_rule = rule
            break
            
        # 2. Nếu rule có quy định thứ -> Check xem hôm nay có nằm trong đó không
        # Ví dụ days_of_week lưu "5,6" (Thứ 7, CN)
        if rule.days_of_week and current_weekday in rule.days_of_week.split(','):
            selected_rule = rule
            break

    # --- D. Áp dụng giá từ Rule (CHỈ ÁP DỤNG GIÁ NGÀY) ---
    if selected_rule:
        # Chỉ cập nhật giá ngày từ Rule
        if selected_rule.price_daily > 0:
            prices['p_night'] = float(selected_rule.price_daily)
            
        # --- QUAN TRỌNG: KHÔNG lấy giá giờ từ Rule nữa (vì bảng PriceRule không có cột này) ---
        # Giá giờ giữ nguyên theo config của Room (đã lấy ở bước A)

        prices['is_special'] = True
        prices['rule_name'] = selected_rule.name

    return prices

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

# =======================================================
# 4. HÀM LOGIC CHÍNH (MAIN FUNCTION) - ĐÃ SỬA
# =======================================================
def calculate_complex_hotel_bill(check_in, check_out, room, rental_type='hourly', 
                                 expected_check_in=None, expected_check_out=None):
    """
    Hàm tính tiền chuẩn xác (Fix lỗi phụ thu hàng trăm giờ):
    1. Base Fee (Tiền phòng): Tính số ĐÊM dựa trên khoảng ngày rộng nhất (để thu đủ nếu ở lố ngày).
    2. Surcharge (Phụ thu): CHỈ tính số GIỜ lố trong ngày check-in/check-out thực tế.
    """
    
    # Cấu hình giờ chuẩn của khách sạn
    STD_IN_HOUR = 14  # 14:00
    STD_OUT_HOUR = 12 # 12:00

    prices = get_effective_room_prices(room, check_in)
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
        nightly_breakdown = get_nightly_price_breakdown(
            room,
            datetime.combine(bill_start_date, time(14, 0)),
            datetime.combine(bill_end_date, time(12, 0)),
        )
        nights = len(nightly_breakdown)
        base_fee = sum(line['amount'] for line in nightly_breakdown)
        total_fee += base_fee
        
        breakdown.append({
            "label": f"Tiền phòng{rule_tag}",
            "detail": f"{nights} đêm (Từ {bill_start_date.strftime('%d/%m')} đến {bill_end_date.strftime('%d/%m')})",
            "amount": base_fee
        })
        for line in nightly_breakdown:
            breakdown.append({
                "label": f"Giá đêm {line['business_date'].strftime('%d/%m')}",
                "detail": "Giá theo rule hiệu lực của đêm này",
                "amount": line['amount'],
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
