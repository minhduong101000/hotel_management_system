"""Chặn đồng hồ máy quay lại controllers/services/models.

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
FOLDERS = ("controllers", "services", "models")

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


def test_no_ambient_clock_in_controllers_services_and_models():
    offenders = _scan()

    assert not offenders, (
        "Đồng hồ máy sai cả hai vế của hợp đồng thời gian. Dùng "
        + REPLACEMENTS
        + ".\n"
        + "\n".join(offenders)
    )


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
