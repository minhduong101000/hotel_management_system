from datetime import datetime, time, timedelta
import math
from sqlalchemy import and_

# Import model PriceRule
# Lưu ý: Cần chắc chắn đường dẫn import đúng với cấu trúc thư mục của bạn
from models.price_rule import PriceRule 

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
    initial_hours_val = int(getattr(room, 'initial_hours', 1)) # Mặc định block đầu là 1 tiếng

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
    candidate_rules = PriceRule.query.filter(
        and_(
            PriceRule.room_type == room.room_type, 
            PriceRule.is_active == True,
            # Kiểm tra ngày nằm trong khoảng hiệu lực (Start -> End)
            PriceRule.start_date <= check_date_obj,
            PriceRule.end_date >= check_date_obj
        )
    ).order_by(PriceRule.priority.desc()).all()

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
# 4. HÀM LOGIC CHÍNH (MAIN FUNCTION)
# =======================================================
def calculate_complex_hotel_bill(check_in, check_out, room, rental_type='hourly'):
    """
    Hàm tính tiền tổng hợp:
    1. Lấy giá chuẩn (đã áp dụng Rule Lễ/Tết cho giá ngày).
    2. Nếu thuê giờ: Tính giá giờ -> So sánh giá ngày -> Chọn phương án rẻ hoặc đúng luật.
    3. Nếu thuê ngày (hoặc bị chuyển từ giờ sang): Tính đêm + Phụ thu Check-in/out.
    """
    
    # B1: Lấy cấu hình giá (Đã check Lễ/Tết)
    prices = get_effective_room_prices(room, check_in)
    
    # Biến để hiển thị tên rule (nếu có)
    rule_tag = f" ({prices['rule_name']})" if prices['is_special'] else ""
    
    total_fee = 0.0
    breakdown = []
    
    # Cấu hình giờ chuẩn
    STD_IN = 14  # 14:00
    STD_OUT = 12 # 12:00

    # Cờ xác định có dùng luật ngày hay không
    use_daily_rule = (rental_type == 'daily')

    # ====================================================
    # CASE A: KHÁCH THUÊ GIỜ (HOURLY)
    # ====================================================
    if rental_type == 'hourly':
        # Tính tiền giờ thuần túy
        raw_fee, billed_hours, note = calculate_raw_hourly_fee(check_in, check_out, prices)
        
        # --- LOGIC QUAN TRỌNG: CEILING CHECK (KIỂM TRA TRẦN) ---
        # Nếu tiền giờ > tiền 1 đêm (theo giá thời điểm đó) -> Chuyển sang tính ngày
        if raw_fee > prices['p_night']:
            use_daily_rule = True 
            # Không append breakdown vội, để xuống dưới tính lại theo ngày
        else:
            total_fee = raw_fee
            breakdown.append({
                "label": f"Tiền giờ{rule_tag}",
                "detail": note,
                "amount": total_fee
            })

    # ====================================================
    # CASE B: KHÁCH THUÊ NGÀY (HOẶC BỊ CHUYỂN TỪ GIỜ SANG)
    # ====================================================
    if use_daily_rule:
        # Nếu bị chuyển từ giờ sang, thêm 1 dòng log giải thích
        if rental_type == 'hourly':
            breakdown.append({
                "label": "Tự động chuyển đổi",
                "detail": "Tiền giờ > Giá đêm. Tính theo giá đêm có lợi hơn.",
                "amount": 0
            })

        # 1. Tính tiền đêm cơ bản
        # Logic: check_out date - check_in date
        nights = (check_out.date() - check_in.date()).days
        if nights < 1: nights = 1 # Tối thiểu 1 đêm
        
        base_fee = nights * prices['p_night']
        total_fee += base_fee
        
        breakdown.append({
            "label": f"Tiền phòng{rule_tag}",
            "detail": f"{nights} đêm (Chuẩn 14h-12h)",
            "amount": base_fee
        })

        # 2. Phụ thu Check-in Sớm (Early Check-in)
        # So sánh giờ check-in thực tế vs 14:00 cùng ngày
        std_checkin_time = datetime.combine(check_in.date(), time(STD_IN, 0))
        if check_in < std_checkin_time:
            diff = std_checkin_time - check_in
            early_hours = diff.total_seconds() / 3600.0
            
            ratio, r_note = get_surcharge_ratio(early_hours)
            if ratio > 0:
                surcharge = prices['p_night'] * ratio
                total_fee += surcharge
                breakdown.append({
                    "label": "Phụ thu nhận sớm",
                    "detail": f"Sớm {early_hours:.1f}h ({r_note})",
                    "amount": surcharge
                })

        # 3. Phụ thu Check-out Muộn (Late Check-out)
        # So sánh giờ check-out thực tế vs 12:00 cùng ngày
        std_checkout_time = datetime.combine(check_out.date(), time(STD_OUT, 0))
        if check_out > std_checkout_time:
            diff = check_out - std_checkout_time
            late_hours = diff.total_seconds() / 3600.0
            
            ratio, r_note = get_surcharge_ratio(late_hours)
            if ratio > 0:
                surcharge = prices['p_night'] * ratio
                total_fee += surcharge
                breakdown.append({
                    "label": "Phụ thu trả muộn",
                    "detail": f"Muộn {late_hours:.1f}h ({r_note})",
                    "amount": surcharge
                })

    return total_fee, breakdown