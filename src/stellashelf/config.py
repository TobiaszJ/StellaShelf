"""StellaShelf centralized configuration.

All default paths and application constants are defined here.
"""

import os
from pathlib import Path

# Default database directory (hidden directory in user home)
DEFAULT_APP_DIR = Path.home() / ".stellashelf"

# Default database file path
DEFAULT_DB_PATH = DEFAULT_APP_DIR / "stellashelf.db"

# Default server settings — changed to 127.0.0.1 for security
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8321

# API key authentication
API_KEY_FILE = DEFAULT_APP_DIR / "api_key.txt"

# Known camera folder names used for path-based equipment extraction.
# Can be overridden via the STELLASHELF_KNOWN_CAMERAS environment variable
# (comma-separated list).
_DEFAULT_KNOWN_CAMERAS = [
    "ASI183MMPro",
    "ASI2600MMPro",
    "ASI2600MMPro2",
    "ASI294MMPro",
    "ASI533MCPro",
]

KNOWN_CAMERAS = frozenset(
    os.environ.get("STELLASHELF_KNOWN_CAMERAS", ",".join(_DEFAULT_KNOWN_CAMERAS)).split(",")
)


def get_db_path(app_dir: Path | None = None) -> Path:
    """Get the database file path, creating the app directory if needed."""
    target_dir = app_dir or DEFAULT_APP_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / "stellashelf.db"
