"""Mọi tệp tải từ CDN phải có `integrity` + `crossorigin`.

Trình duyệt chạy bất cứ thứ gì CDN trả về. Không có `integrity`, một lần
jsdelivr hoặc cdnjs bị chèn mã là mã đó chạy trong phiên của lễ tân, với quyền
đầy đủ — kể cả đọc token CSRF ở thẻ meta trong cùng trang.

`crossorigin` là bắt buộc đi kèm: thiếu nó thì trình duyệt tải tệp ở chế độ
no-cors, không đọc được nội dung để băm, nên **bỏ qua luôn `integrity`** —
trang vẫn chạy, và ta tưởng đã được bảo vệ trong khi không.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Nguồn CDN thật sự phục vụ mã chạy được. `fonts.googleapis.com` cấp CSS sinh
# động (khác nhau theo trình duyệt) nên không băm cố định được, và
# `fonts.gstatic.com` chỉ là preconnect — cả hai nằm ngoài lưới này.
CODE_CDN_HOSTS = ("cdn.jsdelivr.net", "cdnjs.cloudflare.com")

TAG = re.compile(r"<(?:link|script)\b[^>]*>", re.I | re.S)


def _templates():
    return sorted(ROOT.glob("templates/**/*.html"))


def _code_cdn_tags():
    found = []
    for path in _templates():
        source = path.read_text(encoding="utf-8")
        for tag in TAG.findall(source):
            if any(host in tag for host in CODE_CDN_HOSTS):
                found.append((path.relative_to(ROOT).as_posix(), tag))
    return found


def test_the_project_still_loads_something_from_a_cdn():
    """Lưới này chỉ có nghĩa khi còn thứ để canh.

    Nếu sau này vendor hết về `static/` thì test dưới sẽ xanh một cách rỗng
    tuếch — ca này biến điều đó thành một thất bại nhìn thấy được, để người ta
    xoá lưới một cách có ý thức thay vì tưởng nó vẫn đang bảo vệ.
    """
    assert _code_cdn_tags(), (
        "Không còn thẻ CDN nào. Nếu đã vendor hết thì xoá luôn tệp test này."
    )


def test_every_cdn_asset_is_pinned_with_integrity_and_crossorigin():
    offenders = []
    for rel, tag in _code_cdn_tags():
        if "integrity=" not in tag:
            offenders.append(f"{rel}: thiếu integrity — {tag[:90]}")
        elif "crossorigin" not in tag:
            offenders.append(f"{rel}: có integrity nhưng thiếu crossorigin — {tag[:90]}")

    assert not offenders, "\n".join(offenders)


def test_integrity_values_are_sha384_base64():
    """Bắt lỗi gõ nhầm/cắt cụt: một hash sai làm trình duyệt TỪ CHỐI tệp, và
    trang gãy hoàn toàn chứ không gãy nhẹ."""
    pattern = re.compile(r'integrity="sha384-[A-Za-z0-9+/]{64}"')
    for rel, tag in _code_cdn_tags():
        assert pattern.search(tag), f"{rel}: integrity không đúng dạng sha384 — {tag[:90]}"
