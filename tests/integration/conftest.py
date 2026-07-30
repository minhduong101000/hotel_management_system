import os
import re
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url


_TEST_DATABASE_PATTERN = re.compile(r"(^|[_-])test([_-]|$)", re.IGNORECASE)


@pytest.fixture()
def mysql_database_url():
    base_url_value = os.environ.get("TEST_MYSQL_DATABASE_URL")
    if not base_url_value:
        pytest.skip("Cần TEST_MYSQL_DATABASE_URL để chạy kiểm thử MySQL.")

    base_url = make_url(base_url_value)
    base_database = base_url.database or ""
    if not _TEST_DATABASE_PATTERN.search(base_database):
        pytest.fail(
            "TEST_MYSQL_DATABASE_URL phải trỏ tới database có từ 'test' "
            "được phân tách bằng '_' hoặc '-'."
        )

    database_name = f"{base_database}_{uuid.uuid4().hex[:8]}"
    if not _TEST_DATABASE_PATTERN.search(database_name):
        pytest.fail("Tên database tạm không thuộc allowlist kiểm thử.")

    admin_engine = create_engine(base_url.set(database=None), isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as connection:
            connection.exec_driver_sql(
                f"CREATE DATABASE `{database_name}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )

        yield base_url.set(database=database_name).render_as_string(
            hide_password=False
        )
    finally:
        with admin_engine.connect() as connection:
            connection.exec_driver_sql(f"DROP DATABASE IF EXISTS `{database_name}`")
        admin_engine.dispose()
