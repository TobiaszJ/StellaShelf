#!/usr/bin/env python
"""Migrate camera/telescope metadata from filepath structure.

Reads all frames from the StellaShelf database, extracts camera and telescope
names from the file path using the Astro/astro/{CAMERA}/{TELESCOPE}/ pattern,
and updates instrume/telescop columns where the stored value differs from
the path-derived value (typically generic FITS header names).

Usage:
    python scripts/migrate_path_metadata.py [--db PATH] [--dry-run]
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from stellashelf.config import get_db_path
from stellashelf.db import Frame, init_db
from stellashelf.scanner import _extract_camera_from_path, _extract_telescope_from_path


def _is_generic(value: str | None) -> bool:
    """Return True if the value looks like a generic FITS header name."""
    if not value:
        return True
    lower = value.lower()
    generic_markers = (
        "asi camera",
        "poth",
        "unknown",
        "generic",
        "zwo camera",
    )
    return any(marker in lower for marker in generic_markers)


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    db_arg = None
    for i, arg in enumerate(sys.argv):
        if arg == "--db" and i + 1 < len(sys.argv):
            db_arg = sys.argv[i + 1]

    db_path = Path(db_arg) if db_arg else get_db_path()
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        sys.exit(1)

    engine, SessionLocal = init_db(db_path)
    mode = "DRY RUN" if dry_run else "LIVE"
    print(f"Path metadata migration [{mode}] — {db_path}")

    updated_camera = 0
    updated_telescope = 0
    skipped_no_path = 0
    skipped_already_good = 0

    with SessionLocal() as session:
        frames = session.query(Frame).all()
        total = len(frames)
        print(f"Scanning {total} frames...")

        for frame in frames:
            fp = Path(frame.filepath)
            path_camera = _extract_camera_from_path(fp)
            path_telescope = _extract_telescope_from_path(fp)

            camera_changed = False
            telescope_changed = False

            if path_camera and frame.instrume != path_camera:
                frame.instrume = path_camera
                camera_changed = True
                updated_camera += 1

            if path_telescope and frame.telescop != path_telescope:
                frame.telescop = path_telescope
                telescope_changed = True
                updated_telescope += 1

            if not camera_changed and not telescope_changed:
                if not path_camera and not path_telescope:
                    skipped_no_path += 1
                else:
                    skipped_already_good += 1

        if not dry_run and (updated_camera or updated_telescope):
            session.commit()
            print("Changes committed.")
        elif dry_run:
            print("Dry run — no changes written.")

    print(f"\nSummary:")
    print(f"  Total frames scanned:    {total}")
    print(f"  Cameras updated:         {updated_camera}")
    print(f"  Telescopes updated:      {updated_telescope}")
    print(f"  Already correct:         {skipped_already_good}")
    print(f"  No path metadata:        {skipped_no_path}")


if __name__ == "__main__":
    main()
