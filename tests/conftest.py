from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = TESTS_DIR / "fixtures"


@pytest.fixture
def db_path(tmp_path):
    """Provide a temporary database path for tests."""
    return tmp_path / "test.db"


@pytest.fixture
def fixtures_dir():
    """Provide the test fixtures directory path, skipping if not available."""
    if not FIXTURES_DIR.exists():
        pytest.skip("Test fixtures directory not available")
    return FIXTURES_DIR
