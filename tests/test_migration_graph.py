import os
from pathlib import Path
import subprocess
import sys

from alembic.config import Config
from alembic.script import ScriptDirectory


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"


def load_script_directory():
    config = Config(str(MIGRATIONS_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    return ScriptDirectory.from_config(config)


def test_migration_graph_has_one_head_containing_both_feature_branches():
    script = load_script_directory()
    heads = script.get_heads()

    assert len(heads) == 1

    revisions = {
        revision.revision
        for revision in script.iterate_revisions(heads[0], "base")
    }
    assert "a6b0c4d8e1f3" in revisions
    assert "c8d2e3f4a5b6" in revisions


def test_every_migration_revision_is_reachable_from_the_only_head():
    script = load_script_directory()
    head = script.get_heads()[0]
    reachable = {
        revision.revision for revision in script.iterate_revisions(head, "base")
    }
    all_revisions = {revision.revision for revision in script.walk_revisions()}

    assert reachable == all_revisions


def test_offline_upgrade_sql_can_be_generated_through_the_merged_head():
    environment = os.environ.copy()
    environment.update(
        {
            "DATABASE_URL": "mysql+pymysql://migration:test@localhost/migration_test",
            "PYTHONIOENCODING": "utf-8",
        }
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "flask",
            "--app",
            "app",
            "db",
            "upgrade",
            "--sql",
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "d9e3f4a5b6c7" in result.stdout
