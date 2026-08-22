"""Chặn đồng hồ máy quay lại controllers/services/models/scripts.

Đây là lưới giữ cho lớp lỗi 17-08 không tái phát. Mọi lời gọi "bây giờ" không
tham số đều lấy giờ đồng hồ tiến trình nên sai CẢ HAI vế của hợp đồng thời
gian — nó không phải giờ nghiệp vụ để so với *_expected, cũng không đảm bảo là
UTC để ghi timestamp:

- ``datetime`` chấm ``now()``   -> giờ máy, không phải giờ nghiệp vụ lẫn UTC
- ``datetime`` chấm ``today()`` -> cùng vấn đề, chỉ khác là bị dùng để lấy NGÀY
- ``date`` chấm ``today()``     -> ngày theo giờ máy: nhập kho 00:30 bị đóng
  dấu ngày hôm trước và sinh mã lô sai ngày
- ``utcnow()``                  -> đúng UTC nhưng deprecated và naive-ngầm;
  dùng time_service.utc_now_naive() để chỉ có một nguồn duy nhất

``datetime.now(timezone.utc)`` CÓ tham số nên hợp lệ (time_service.utc_now
đang dùng) và không bị bắt.

Chính docstring này viết tách chuỗi để lưới không tự bắt file test.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = ("controllers", "services", "models", "scripts")

# Chỉ bắt lời gọi TRẦN: có tham số (datetime.now(timezone.utc)) là hợp lệ.
AMBIENT_CLOCK = re.compile(
    r"\b(?:datetime\.now|datetime\.today|date\.today|datetime\.utcnow|utcnow)\(\s*\)"
)

REPLACEMENTS = (
    "time_service.business_now_naive() khi so với *_expected, "
    "time_service.business_today() khi cần NGÀY nghiệp vụ, "
    "time_service.utc_now_naive() khi ghi timestamp hệ thống"
)


def _scan(folders=FOLDERS):
    offenders = []
    for folder in folders:
        for path in sorted((ROOT / folder).rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            for lineno, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1
            ):
                if AMBIENT_CLOCK.search(line):
                    offenders.append(f"{rel}:{lineno}: {line.strip()}")
    return offenders


def test_no_ambient_clock_in_the_scanned_folders():
    offenders = _scan()

    assert not offenders, (
        "Đồng hồ máy sai cả hai vế của hợp đồng thời gian. Dùng "
        + REPLACEMENTS
        + ".\n"
        + "\n".join(offenders)
    )


DB_SERVER_CLOCK = re.compile(r"db\.func\.now\(\s*\)")


def _scan_db_clock():
    offenders = []
    for path in sorted((ROOT / "models").rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if DB_SERVER_CLOCK.search(line):
                offenders.append(f"{rel}:{lineno}: {line.strip()}")
    return offenders


def test_no_database_server_clock_in_models():
    """`db.func.now()` lấy giờ của MÁY CHỦ MYSQL, không phải của ứng dụng.

    Hôm nay nó đúng, nhưng đúng do trùng hợp: container `db` và container `web`
    tình cờ cùng chạy UTC, và không có gì ghim hay kiểm điều đó. Đặt `TZ` cho
    container db, hay chuyển sang MySQL dịch vụ ở vùng khác, là 15 cột lặng lẽ
    lệch vài giờ — trong đó `payments.created_at` quyết định ranh giới ngày của
    Sổ Quỹ và trần hoàn tiền.

    Hợp đồng thời gian nói `time_service` là nguồn DUY NHẤT. Một nguồn thứ hai
    nằm ngoài tiến trình Python thì không còn là duy nhất nữa.
    """
    offenders = _scan_db_clock()

    assert not offenders, (
        "Giờ máy chủ MySQL không phải nguồn thời gian. Dùng "
        "time_service.utc_now_naive cho cột timestamp hệ thống, "
        "time_service.business_today cho cột NGÀY nghiệp vụ.\n"
        + "\n".join(offenders)
    )


def test_the_db_clock_grid_matches_the_real_spelling():
    """Lưới chỉ có giá trị nếu nó khớp đúng cách viết đã từng có trong repo."""
    for snippet in (
        "    created_at = db.Column(db.DateTime, default=db.func.now())",
        "    updated_at = db.Column(db.DateTime, onupdate=db.func.now())",
        "    created_at = db.Column(db.DateTime, default=db.func.now( ))",
    ):
        assert DB_SERVER_CLOCK.search(snippet), f"lưới bỏ lọt {snippet.strip()}"


def test_the_grid_recognises_every_forbidden_spelling():
    """Lưới chỉ có giá trị nếu nó thật sự khớp từng cách viết bị cấm."""
    for snippet in (
        "    stamp = datetime.now()",
        "    stamp = datetime.today()",
        "    day = date.today()",
        "    stamp = datetime.utcnow()",
        "    stamp = datetime.now( )",
    ):
        assert AMBIENT_CLOCK.search(snippet), f"lưới bỏ lọt {snippet.strip()}"


def test_the_grid_does_not_flag_the_legitimate_aware_call():
    """time_service.utc_now() dùng datetime.now(timezone.utc) — phải cho qua,
    nếu không lưới sẽ ép người ta viết cách tệ hơn."""
    for snippet in (
        "    return datetime.now(timezone.utc)",
        "    return datetime.now(tz=_business_tz())",
        "    created_at = db.Column(db.DateTime, default=db.func.now())",
        "    on_date = on_date or time_service.business_today()",
    ):
        assert not AMBIENT_CLOCK.search(snippet), f"lưới bắt oan {snippet.strip()}"
