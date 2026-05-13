"""StellaShelf CLI entry point."""

import click


@click.group()
@click.version_option()
def main():
    """StellaShelf — Astrophotography DAM & Processing Hub."""
    pass


@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--recursive/--no-recursive", default=True, help="Scan subdirectories recursively")
@click.option("--dry-run/--no-dry-run", default=False, help="Show what would be scanned without writing to DB")
def scan(path: str, recursive: bool, dry_run: bool) -> None:
    """Scan a directory for FITS/XISF files and import metadata."""
    click.echo(f"Scanning {path} (recursive={recursive}, dry_run={dry_run})...")
    # TODO: implement scanner


@main.command()
@click.option("--host", default="0.0.0.0", help="Bind address")
@click.option("--port", default=8080, type=int, help="Bind port")
@click.option("--reload/--no-reload", default=False, help="Enable auto-reload for development")
def serve(host: str, port: int, reload: bool) -> None:
    """Start the StellaShelf web UI."""
    click.echo(f"Starting StellaShelf on {host}:{port} (reload={reload})...")
    # TODO: implement server


if __name__ == "__main__":
    main()