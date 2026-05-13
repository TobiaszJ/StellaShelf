"""StellaShelf CLI — scan, import, and serve."""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from stellashelf.db import init_db, Session as ObsSession, Target, Frame, Camera, Telescope, CalibrationFile
from stellashelf.scanner import scan_directory, generate_group_key, find_fits_files

console = Console()


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

    # Scan all FITS files
    frames = scan_directory(root, recursive=recursive, dry_run=dry_run, verbose=verbose)

    if dry_run:
        console.print("\n[yellow]Dry run — no data written to database.[/yellow]")
        _print_scan_summary(frames)
        return

    # Import into database
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine, SessionLocal = init_db(db_path)

    with SessionLocal() as session:
        # Track equipment we've seen
        cameras_seen: dict[str, int] = {}
        telescopes_seen: dict[str, int] = {}
        targets_seen: dict[str, int] = {}
        sessions_seen: dict[str, int] = {}
        cal_files_seen: int = 0

        imported = 0
        skipped = 0

        for frame in frames:
            # Auto-detect and create equipment
            camera_id = None
            if frame.instrume:
                if frame.instrume not in cameras_seen:
                    # Check if camera exists
                    existing = session.query(Camera).filter_by(name=frame.instrume).first()
                    if existing:
                        cameras_seen[frame.instrume] = existing.id
                    else:
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
                    existing = session.query(Telescope).filter_by(name=frame.telescop).first()
                    if existing:
                        telescopes_seen[frame.telescop] = existing.id
                    else:
                        telescope = Telescope(
                            name=frame.telescop,
                            short_name=frame.telescop,
                            focal_length_mm=frame.focal_length_mm,
                        )
                        session.add(telescope)
                        session.flush()
                        telescopes_seen[frame.telescop] = telescope.id
                telescope_id = telescopes_seen[frame.telescop]

            # Handle calibration files: no object name + cal frame type
            if not frame.object_name and frame.frame_type in ("BIAS", "DARK", "FLAT"):
                cal_type = frame.frame_type.lower()
                cal = CalibrationFile(
                    camera_id=camera_id,
                    cal_type=cal_type,
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

            # Create/get target
            target_id = None
            obj_name = frame.object_name.strip() if frame.object_name else "UNKNOWN"
            if obj_name and obj_name != "UNKNOWN":
                if obj_name not in targets_seen:
                    existing = session.query(Target).filter_by(name=obj_name).first()
                    if existing:
                        targets_seen[obj_name] = existing.id
                    else:
                        target = Target(name=obj_name)
                        session.add(target)
                        session.flush()
                        targets_seen[obj_name] = target.id
                target_id = targets_seen.get(obj_name)

            # Check for duplicate
            existing_frame = session.query(Frame).filter_by(filepath=str(frame.filepath)).first()
            if existing_frame:
                skipped += 1
                continue

            # Generate group key and create/get session
            group_key = generate_group_key(frame)
            obs_id = sessions_seen.get(group_key)
            if obs_id is None and target_id is not None:
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

            # Create frame record
            db_frame = Frame(
                session_id=obs_id,
                filename=frame.filename,
                filepath=str(frame.filepath),
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

        session.commit()

        # Recalculate session statistics
        console.print("\n[yellow]Recalculating session statistics...[/yellow]")
        for s in session.query(ObsSession).all():
            frames = session.query(Frame).filter_by(session_id=s.id).all()
            s.frame_count = len(frames)
            s.total_exposure_s = sum(f.exposure or 0 for f in frames)
            s.total_exposure_h = s.total_exposure_s / 3600
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

    for f in frames[:50]:  # Show first 50
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