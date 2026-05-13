"""StellaShelf CLI — scan, import, and serve."""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from sqlalchemy import text

from stellashelf.db import init_db, Session as ObsSession, Target, Frame, Camera, Telescope, CalibrationFile
from stellashelf.scanner import scan_directory, generate_group_key, find_fits_files

console = Console()

BATCH_SIZE = 500  # Commit every N frames to keep memory low and enable partial recovery


@click.group()
@click.version_option()
def main():
    """StellaShelf — Astrophotography DAM & Processing Hub."""
    pass


@main.command()
@click.argument("path", type=click.Path(exists=True, file_okay=False))
@click.option("--db", default="~/stellashelf/stellashelf.db", help="Path to SQLite database")
@click.option("--recursive/--no-recursive", default=True, help="Scan subdirectories")
@click.option("--dry-run", is_flag=True, help="Scan only, don't write to database")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
def scan(path: str, db: str, recursive: bool, dry_run: bool, verbose: bool):
    """Scan a directory for FITS files and import metadata."""
    root = Path(path).resolve()
    db_path = Path(db).expanduser().resolve()

    if not root.exists():
        console.print(f"[red]Path not found: {root}[/red]")
        sys.exit(1)

    console.print(f"[bold cyan]StellaShelf[/bold cyan] scanning: {root}")
    console.print(f"Database: {db_path}")

    frames = scan_directory(root, recursive=recursive, dry_run=dry_run, verbose=verbose)

    if dry_run:
        console.print("\n[yellow]Dry run — no data written to database.[/yellow]")
        _print_scan_summary(frames)
        return

    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine, SessionLocal = init_db(db_path)

    with SessionLocal() as session:
        cameras_seen: dict[str, int] = {}
        telescopes_seen: dict[str, int] = {}
        targets_seen: dict[str, int] = {}
        sessions_seen: dict[str, int] = {}
        cal_files_seen: int = 0

        imported = 0
        skipped = 0
        batch_count = 0

        # Pre-load all existing frames into a set for fast duplicate check
        existing_paths = set()
        for row in session.query(Frame.filepath).all():
            existing_paths.add(row[0])

        # Pre-load all existing sessions by group_key
        for row in session.query(ObsSession.id, ObsSession.group_key).all():
            sessions_seen[row[1]] = row[0]

        # Pre-load all existing equipment
        for row in session.query(Camera.id, Camera.name).all():
            cameras_seen[row[1]] = row[0]
        for row in session.query(Telescope.id, Telescope.name).all():
            telescopes_seen[row[1]] = row[0]
        for row in session.query(Target.id, Target.name).all():
            targets_seen[row[1]] = row[0]

        for frame in frames:
            # Equipment
            camera_id = None
            if frame.instrume:
                if frame.instrume not in cameras_seen:
                    camera = Camera(
                        name=frame.instrume,
                        short_name=frame.instrume.replace("ZWO ", "").replace("ASI Camera", "ASI"),
                        pixel_size_um=frame.pixel_size_um,
                    )
                    session.add(camera)
                    session.flush()
                    cameras_seen[frame.instrume] = camera.id
                camera_id = cameras_seen[frame.instrume]

            telescope_id = None
            if frame.telescop:
                if frame.telescop not in telescopes_seen:
                    telescope = Telescope(
                        name=frame.telescop,
                        short_name=frame.telescop,
                        focal_length_mm=frame.focal_length_mm,
                    )
                    session.add(telescope)
                    session.flush()
                    telescopes_seen[frame.telescop] = telescope.id
                telescope_id = telescopes_seen[frame.telescop]

            # Calibration files: no object + cal frame type → separate table
            if not frame.object_name and frame.frame_type in ("BIAS", "DARK", "FLAT"):
                cal = CalibrationFile(
                    camera_id=camera_id,
                    cal_type=frame.frame_type.lower(),
                    exposure_s=frame.exposure,
                    gain=frame.gain,
                    binning=frame.binning,
                    ccd_temp=frame.ccd_temp,
                    filepath=str(frame.filepath),
                    filename=frame.filename,
                )
                session.add(cal)
                cal_files_seen += 1
                continue

            # Target
            target_id = None
            obj_name = frame.object_name.strip() if frame.object_name else ""
            if obj_name and obj_name != "UNKNOWN":
                if obj_name not in targets_seen:
                    target = Target(name=obj_name)
                    session.add(target)
                    session.flush()
                    targets_seen[obj_name] = target.id
                target_id = targets_seen.get(obj_name)

            # Duplicate check via pre-loaded set
            fp = str(frame.filepath)
            if fp in existing_paths:
                skipped += 1
                continue
            existing_paths.add(fp)

            # Session: create if needed
            group_key = generate_group_key(frame)
            obs_id = sessions_seen.get(group_key)

            if obs_id is None:
                # Sessions always get a target_id; use UNKNOWN target if needed
                if target_id is None:
                    if "UNKNOWN" not in targets_seen:
                        unk = Target(name="UNKNOWN")
                        session.add(unk)
                        session.flush()
                        targets_seen["UNKNOWN"] = unk.id
                    target_id = targets_seen["UNKNOWN"]

                existing_session = session.query(ObsSession).filter_by(group_key=group_key).first()
                if existing_session:
                    obs_id = existing_session.id
                    sessions_seen[group_key] = obs_id
                else:
                    obs = ObsSession(
                        target_id=target_id,
                        camera_id=camera_id,
                        telescope_id=telescope_id,
                        date_obs=frame.date_obs,
                        group_key=group_key,
                        path=str(frame.filepath.parent),
                        status="raw",
                    )
                    session.add(obs)
                    session.flush()
                    obs_id = obs.id
                    sessions_seen[group_key] = obs_id

            # Frame record
            db_frame = Frame(
                session_id=obs_id,
                filename=frame.filename,
                filepath=fp,
                file_size=frame.file_size,
                frame_type=frame.frame_type or "LIGHT",
                object_name=obj_name,
                instrume=frame.instrume or "",
                telescop=frame.telescop or "",
                filter_name=frame.filter_name or "",
                exposure=frame.exposure,
                gain=frame.gain,
                ccd_temp=frame.ccd_temp,
                binning=frame.binning,
                date_obs=frame.date_obs,
                date_local=frame.date_local,
                width=frame.width,
                height=frame.height,
                pixel_size_um=frame.pixel_size_um,
                focal_length_mm=frame.focal_length_mm,
                ra_deg=frame.ra_deg,
                dec_deg=frame.dec_deg,
                site_name=frame.site_name or "",
                observer=frame.observer or "",
                creator=frame.creator or "",
            )
            session.add(db_frame)
            imported += 1
            batch_count += 1

            # FIX #2: Batch commits to keep memory low
            if batch_count >= BATCH_SIZE:
                session.commit()
                console.print(f"  [dim]Checkpoint: {imported} imported, {skipped} skipped[/dim]")
                batch_count = 0

        session.commit()

        # Recalculate session stats with raw SQL (much faster than loading ORM objects)
        console.print("\n[yellow]Recalculating session statistics...[/yellow]")
        session.execute(text(
            """
            UPDATE sessions SET
                frame_count = (SELECT COUNT(*) FROM frames WHERE frames.session_id = sessions.id),
                total_exposure_s = COALESCE((SELECT SUM(frames.exposure) FROM frames WHERE frames.session_id = sessions.id), 0),
                total_exposure_h = COALESCE((SELECT SUM(frames.exposure) FROM frames WHERE frames.session_id = sessions.id), 0) / 3600.0
            """
        ))
        session.commit()

    console.print(f"\n[green]✓ Imported {imported} frames ({skipped} duplicates skipped)[/green]")
    console.print(f"  [cyan]Targets:[/cyan] {len(targets_seen)}")
    console.print(f"  [cyan]Sessions:[/cyan] {len(sessions_seen)}")
    console.print(f"  [cyan]Cameras:[/cyan] {len(cameras_seen)}")
    console.print(f"  [cyan]Telescopes:[/cyan] {len(telescopes_seen)}")
    console.print(f"  [cyan]Calibration files:[/cyan] {cal_files_seen}")


@main.command()
@click.option("--db", default="~/stellashelf/stellashelf.db", help="Path to SQLite database")
def stats(db: str):
    """Show database statistics."""
    db_path = Path(db).expanduser().resolve()
    if not db_path.exists():
        console.print(f"[red]Database not found: {db_path}[/red]")
        console.print("Run [bold]stellashelf scan[/bold] first.")
        sys.exit(1)

    engine, SessionLocal = init_db(db_path)
    with SessionLocal() as session:
        targets = session.query(Target).count()
        frames = session.query(Frame).count()
        cameras = session.query(Camera).count()
        telescopes = session.query(Telescope).count()
        cal_files = session.query(CalibrationFile).count()
        observations = session.query(ObsSession).count()

    table = Table(title="StellaShelf Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="green", justify="right")
    table.add_row("Targets", str(targets))
    table.add_row("Sessions", str(observations))
    table.add_row("Frames", str(frames))
    table.add_row("Cameras", str(cameras))
    table.add_row("Telescopes", str(telescopes))
    table.add_row("Calibration files", str(cal_files))
    console.print(table)


@main.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=8321, help="Port to bind to")
@click.option("--db", default="~/stellashelf/stellashelf.db", help="Path to SQLite database")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
def serve(host: str, port: int, db: str, reload: bool):
    """Start the StellaShelf web API server."""
    import uvicorn

    db_path = Path(db).expanduser().resolve()
    console.print(f"[bold cyan]StellaShelf[/bold cyan] starting API server on {host}:{port}")
    console.print(f"Database: {db_path}")

    uvicorn.run(
        "stellashelf.api:app",
        host=host,
        port=port,
        reload=reload,
    )


def _print_scan_summary(frames):
    """Print a summary table of scanned frames."""
    table = Table(title="Scan Results")
    table.add_column("Object", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Camera", style="magenta")
    table.add_column("Filter", style="yellow")
    table.add_column("Exposure", justify="right")
    table.add_column("Date", style="blue")

    for f in frames[:50]:
        table.add_row(
            f.object_name or "-",
            f.frame_type or "-",
            f.instrume or "-",
            f.filter_name or "-",
            f"{f.exposure}s" if f.exposure else "-",
            str(f.date_obs.date()) if f.date_obs else "-",
        )

    console.print(table)
    if len(frames) > 50:
        console.print(f"[dim]... and {len(frames) - 50} more[/dim]")