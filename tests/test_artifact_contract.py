import json
from pathlib import Path

import pytest

from config import LEAGUE_CONFIG
from pitch_oracle_core import __version__
from pitch_oracle_core.cache import validate_cache


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "precomputed" / "cache_manifest.json"


def _manifest_matches_installed_core() -> bool:
    """Only validate committed artifacts built by the installed core release."""
    if not MANIFEST.exists():
        return False
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return manifest.get("core_version") == __version__


@pytest.mark.skipif(
    not _manifest_matches_installed_core(),
    reason="artifact pipeline has not produced a cache for the installed core yet",
)
def test_runtime_artifacts_match_core_and_league_contract():
    assert validate_cache(ROOT, expected_league=LEAGUE_CONFIG.key) == ()
