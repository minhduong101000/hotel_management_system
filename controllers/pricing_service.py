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
# 4. HÀM LOGIC CHÍNH (MAIN FUNCTION) - ĐÃ SỬA
# =======================================================
def calculate_complex_hotel_bill(check_in, check_out, room, rental_type='hourly', 
                                 expected_check_in=None, expected_check_out=None):
    """
    Hàm tính tiền chuẩn xác:
    1. Base Fee: Luôn tính dựa trên thời gian ĐÃ ĐẶT (Booking) để đảm bảo doanh thu (khách đến muộn vẫn phải trả).
    2. Surcharge: Chỉ tính khi khách đến SỚM HƠN booking hoặc về MUỘN HƠN booking.
    """
    
    # --- 1. XÁC ĐỊNH MỐC TÍNH TIỀN PHÒNG (BASE) ---
    # Mặc định lấy theo Booking (Expected). 
    # Nếu không có Booking (khách lẻ) thì lấy theo Thực tế.
    
    base_start = expected_check_in if expected_check_in else check_in
    base_end = expected_check_out if expected_check_out else check_out
    
    # Lấy giá tại thời điểm bắt đầu tính tiền
    prices = get_effective_room_prices(room, base_start)
    rule_tag = f" ({prices['rule_name']})" if prices['is_special'] else ""
    
    total_fee = 0.0
    breakdown = []
    
    use_daily_rule = (rental_type == 'daily')

    # ====================================================
    # PHẦN 1: TÍNH TIỀN PHÒNG CƠ BẢN (THEO BOOKING)
    # ====================================================
    
    # CASE A: THUÊ GIỜ
    if rental_type == 'hourly':
        # Với thuê giờ, thường tính theo thực tế nhiều hơn, nhưng nếu logic của bạn là giữ slot
        # thì vẫn dùng base_start/base_end. 
        # Tuy nhiên, để an toàn và thường gặp: Thuê giờ tính theo range rộng nhất.
        calc_start = min(check_in, base_start)
        calc_end = max(check_out, base_end)
        
        raw_fee, billed_hours, note = calculate_raw_hourly_fee(calc_start, calc_end, prices)
        
        if raw_fee > prices['p_night']:
            use_daily_rule = True
        else:
            total_fee = raw_fee
            breakdown.append({
                "label": f"Tiền giờ{rule_tag}",
                "detail": note,
                "amount": total_fee
            })

    # CASE B: THUÊ NGÀY
    if use_daily_rule:
        if rental_type == 'hourly':
            breakdown.append({
                "label": "Tự động chuyển đổi",
                "detail": "Tiền giờ > Giá đêm. Tính theo giá đêm.",
                "amount": 0
            })

        # Tính số đêm dựa trên BOOKING (để khách đến muộn vẫn thu đủ)
        nights = (base_end.date() - base_start.date()).days
        if nights < 1: nights = 1 
        
        base_fee = nights * prices['p_night']
        total_fee += base_fee
        
        # Format hiển thị giờ
        bk_in_str = base_start.strftime('%d/%m %H:%M')
        bk_out_str = base_end.strftime('%d/%m %H:%M')
        
        breakdown.append({
            "label": f"Tiền phòng{rule_tag}",
            "detail": f"{nights} đêm (Theo lịch đặt: {bk_in_str} - {bk_out_str})",
            "amount": base_fee
        })

        # ====================================================
        # PHẦN 2: TÍNH PHỤ THU (CHỈ KHI VƯỢT KHUNG)
        # ====================================================
        
        total_extra_hours = 0.0
        extra_details = [] 

        # 1. Check-in Sớm: Chỉ tính nếu Thực tế < Dự kiến (Đã bao gồm logic 14:00 nếu dự kiến set là 14:00)
        # Ví dụ: Book 14:00, Vào 10:00 -> Sớm 4h.
        # Ví dụ: Book 14:00, Vào 15:00 -> Không sớm -> Không tính.
        # Ví dụ: Book 10:00 (đã trả phí trước), Vào 10:00 -> Không sớm -> Không tính thêm.
        
        if expected_check_in and check_in < expected_check_in:
            diff = expected_check_in - check_in
            early_h = diff.total_seconds() / 3600.0
            
            # Chỉ tính nếu sớm đáng kể (trên 15p)
            if early_h > 0.2: 
                total_extra_hours += early_h
                extra_details.append(f"Sớm {early_h:.1f}h")

        # 2. Check-out Muộn: Chỉ tính nếu Thực tế > Dự kiến
        # Ví dụ: Book đến 12:00, Ra 14:00 -> Muộn 2h.
        # Ví dụ: Book đến 12:00, Ra 10:00 -> Không muộn -> Không tính.
        
        if expected_check_out and check_out > expected_check_out:
            diff = check_out - expected_check_out
            late_h = diff.total_seconds() / 3600.0
            
            if late_h > 0.2:
                total_extra_hours += late_h
                extra_details.append(f"Muộn {late_h:.1f}h")

        # 3. Tổng hợp Phụ thu
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