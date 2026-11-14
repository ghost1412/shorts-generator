import os
import sys

# Make `engine` importable when pytest runs from any directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


@pytest.fixture(autouse=True)
def _private_transcript_cache(tmp_path, monkeypatch):
    """Tests never read or write the real ~/.shortsflow cache."""
    monkeypatch.setenv("SHORTSFLOW_CACHE_DIR", str(tmp_path / "shortsflow-cache"))
