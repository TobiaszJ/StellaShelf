"""Fix sessions.path to point to the actual session folder.

Computes the longest common prefix directory for all frames in a session.
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from stellashelf.config import get_db_path
from stellashelf.db import Frame, Session, init_db


def common_directory(paths: list[str]) -> str:
    """Find the deepest common parent directory from a list of filepaths."""
    if not paths:
        return ""
    dirs = [Path(p).parent for p in paths]
    if len(dirs) == 1:
        return str(dirs[0])
    # Find common prefix by comparing path parts
    parts_list = [list(d.parts) for d in dirs]
    common = []
    for parts in zip(*parts_list):
        if len(set(parts)) == 1:
            common.append(parts[0])
        else:
            break
    if not common:
        return str(dirs[0])
    return str(Path(*common))


def main() -> None:
    db_path = get_db_path()
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        sys.exit(1)

    engine, SessionLocal = init_db(db_path)
    print(f"Fixing session paths — {db_path}")

    with SessionLocal() as session:
        sessions = session.query(Session).all()
        total = len(sessions)
        updated = 0

        for s in sessions:
            frame_paths = [f.filepath for f in session.query(Frame.filepath).filter(
                Frame.session_id == s.id
            ).all()]

            if not frame_paths:
                continue

            actual_path = common_directory(frame_paths)
            if s.path != actual_path:
                s.path = actual_path
                updated += 1

        session.commit()
        print(f"Updated {updated} of {total} sessions")


if __name__ == "__main__":
    main()
