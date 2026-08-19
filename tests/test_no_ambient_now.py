"""Chặn `datetime.now()` quay lại controllers/services.

Đây là lưới giữ cho lớp lỗi 17-08 không tái phát: `datetime.now()` lấy giờ đồng
hồ máy nên sai CẢ HAI vế của hợp đồng thời gian — nó không phải giờ nghiệp vụ
để so với *_expected, cũng không đảm bảo là UTC để ghi timestamp.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = ("controllers", "services")
# datetime.now(timezone.utc) có tham số nên không khớp — chỉ bắt lời gọi trần.
BARE_NOW = re.compile(r"\bdatetime\.now\(\s*\)")


def test_no_ambient_datetime_now_in_controllers_and_services():
    offenders = []
    for folder in FOLDERS:
        for path in sorted((ROOT / folder).rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if BARE_NOW.search(line):
                    offenders.append(f"{rel}:{lineno}: {line.strip()}")

    assert not offenders, (
        "datetime.now() lấy giờ đồng hồ máy nên sai cả hai vế của hợp đồng thời gian.\n"
        "Dùng time_service.business_now_naive() khi so với *_expected, "
        "hoặc time_service.utc_now_naive() khi ghi timestamp hệ thống.\n"
        + "\n".join(offenders)
    )
