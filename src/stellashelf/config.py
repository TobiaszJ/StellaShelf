"""StellaShelf centralized configuration.

All default paths and application constants are defined here.
"""

from pathlib import Path

# Default database directory (hidden directory in user home)
DEFAULT_APP_DIR = Path.home() / ".stellashelf"

# Default database file path
DEFAULT_DB_PATH = DEFAULT_APP_DIR / "stellashelf.db"

# Default server settings
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8321


def get_db_path(app_dir: Path | None = None) -> Path:
    """Get the database file path, creating the app directory if needed."""
    target_dir = app_dir or DEFAULT_APP_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / "stellashelf.db"
