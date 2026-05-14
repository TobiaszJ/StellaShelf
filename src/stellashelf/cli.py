"""StellaShelf CLI — scan, import, and serve."""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from sqlalchemy import text

from stellashelf.db import init_db, Session as ObsSession, Target, Frame, Camera, Telescope, CalibrationFile
from stellashelf.importer import ImporterService

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

    if dry_run:
        from stellashelf.scanner import scan_directory
        frames = scan_directory(root, recursive=recursive, dry_run=True, verbose=verbose)
        console.print("\n[yellow]Dry run — no data written to database.[/yellow]")
        _print_scan_summary(frames)
        return

    # Use the centralized ImporterService
    importer = ImporterService(db_path)
    stats = importer.import_from_path(root, recursive=recursive)

    console.print(f"\n[green]✓ Imported {stats['imported']} frames ({stats['skipped']} duplicates skipped)[/green]")
    console.print(f"  [cyan]Calibration files:[/cyan] {stats['calibration_files']}")


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