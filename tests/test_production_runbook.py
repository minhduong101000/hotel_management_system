from pathlib import Path


RUNBOOK = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "production-remediation-runbook.md"
)


def test_production_runbook_covers_safe_release_and_rollback_flow():
    assert RUNBOOK.exists()
    source = RUNBOOK.read_text(encoding="utf-8")

    for heading in (
        "## 1. Biến môi trường bắt buộc",
        "## 2. Kiểm tra trước triển khai",
        "## 3. Backup và diễn tập restore",
        "## 4. Nâng cấp Alembic",
        "## 5. Smoke test sau triển khai",
        "## 6. Rollback",
        "## 7. Đối soát dữ liệu",
    ):
        assert heading in source

    for required_text in (
        "APP_ENV",
        "SECRET_KEY",
        "DATABASE_URL",
        "TEST_MYSQL_DATABASE_URL",
        "pytest -m mysql -q",
        "db heads",
        "db upgrade --sql",
        "db upgrade",
        "reconcile-business-data",
        "--backup-acknowledged",
        "docs/reconciliation-runbook.md",
    ):
        assert required_text in source


def test_production_runbook_does_not_embed_known_default_credentials():
    source = RUNBOOK.read_text(encoding="utf-8")

    assert "admin123" not in source
    assert "staff123" not in source
    assert "root:123456" not in source
