from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_migration_history_has_one_baseline_head() -> None:
    api_root = Path(__file__).resolve().parents[3]
    config = Config(api_root / "alembic.ini")
    scripts = ScriptDirectory.from_config(config)

    assert scripts.get_heads() == ["0005_momentum"]
    assert scripts.get_revision("0001_baseline").down_revision is None
    assert scripts.get_revision("0002_identity_data").down_revision == "0001_baseline"
    assert scripts.get_revision("0003_prediction").down_revision == "0002_identity_data"
    assert scripts.get_revision("0004_hardening").down_revision == "0003_prediction"
    assert scripts.get_revision("0005_momentum").down_revision == "0004_hardening"
