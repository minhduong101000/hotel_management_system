"""Cấu hình gunicorn production (spec production-hardening 15-08-2026)."""

import os

bind = "0.0.0.0:8000"
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "60"))

# Access log BẬT ra stdout (mặc định gunicorn tắt) — container gom qua json-file
accesslog = "-"
errorlog = "-"

# Tái sinh worker định kỳ chống rò rỉ bộ nhớ tích lũy
max_requests = 1000
max_requests_jitter = 50
