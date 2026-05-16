# StellaShelf

**Astrophotography Digital Asset Management & Processing Hub**

Open-source tool for cataloging, organizing, and managing deep-sky astrophotography image collections. Scans FITS/XISF headers, groups frames into observation sessions, and provides a modern Vue 3 web interface for browsing your astro archive.

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](https://opensource.org/licenses/AGPL-3.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/TobiaszJ/StellaShelf/actions/workflows/ci.yml/badge.svg)](https://github.com/TobiaszJ/StellaShelf/actions)

## Features

- **FITS Header Scanner**: Recursively scans directories for FITS files, extracts metadata from headers (OBJECT, EXPOSURE, FILTER, coordinates, etc.)
- **Automatic Session Grouping**: Groups frames by target + date + camera + telescope + filter
- **Object Name Normalization**: M51, m51, M 51 → M 51 — prevents duplicate targets
- **Target Merging**: Manual merge per-target + auto-merge-all-duplicates with one click
- **Duplicate Detection**: Automatic detection of targets with the same normalized name
- **Frame Cleanup**: Search by filename or path (wildcards supported), bulk delete from DB
- **Orphan Cleanup**: Automatic removal of empty sessions, targets, and unused equipment
- **SQLite + FTS5**: Serverless database with full-text search, no external dependencies
- **Vue 3 Web Dashboard**: Modern reactive UI with pagination, filtering, and ECharts visualizations
- **REST API**: FastAPI backend with pagination, aggregation, and scan management
- **Calibration File Detection**: Automatically identifies and separates BIAS, DARK, FLAT from light frames
- **Coordinate Parsing**: Converts HMS/DMS strings to decimal degrees for old FITS files

## Quick Start

```bash
# Clone and install
git clone https://github.com/TobiaszJ/StellaShelf.git
cd StellaShelf
python -m venv .venv && source .venv/bin/activate
pip install -e .

# Scan your FITS collection
stellashelf scan /path/to/astro/files

# View statistics
stellashelf stats

# Start web server
stellashelf serve --host 0.0.0.0 --port 8321
# Open http://localhost:8321 in your browser
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `stellashelf scan <path>` | Scan FITS files and import metadata |
| `stellashelf stats` | Show database statistics |
| `stellashelf serve` | Start web API server |

### Scan Options

```bash
stellashelf scan /mnt/data/Astro --recursive --db ~/.stellashelf/stellashelf.db
stellashelf scan /path/to/files --dry-run    # Preview without importing
```

## Architecture

```
src/stellashelf/
├── scanner.py      # FITS header extraction, session grouping, thumbnail generation, platesolving
├── db.py           # SQLAlchemy models (Target, Session, Frame, Camera, Telescope, Setting)
├── importer.py     # Centralized import pipeline (CLI & API)
├── cli.py          # Click CLI commands
├── api.py          # FastAPI REST API + Vue 3 SPA serving (20+ endpoints)
└── config.py       # Centralized configuration (paths, defaults)

frontend-vue/
└── src/
    ├── views/      # 11 Vue views (Dashboard, Targets, TargetDetail, Sessions, SessionDetail, Equipment, Search, Scan, Settings, Platesolve, Help)
    ├── stores/     # Pinia stores (api, scan, theme)
    ├── components/ # Reusable components (StatCard, Pagination)
    └── router/     # Vue Router with 11 routes
```

### Database Schema

- **Target**: Astronomical object (M42, NGC7000, etc.)
- **Session**: One target + one night + one equipment setup
- **Frame**: Individual FITS file with full header metadata
- **Camera/Telescope**: Equipment catalog
- **CalibrationFile**: Master BIAS/DARK/FLAT files
- **Setting**: Key/value application configuration

## Advanced Features

- **Full-Text Search**: FTS5-powered search across targets, sessions, and frames
- **Object Type Badges**: Color-coded labels for Galaxy, Nebula, Star, Cluster, etc.
- **Equipment Catalog**: Tab-based view for cameras, telescopes, and filters with sorting
- **Session Aggregates**: Frame type counts and exposure per filter on session detail pages
- **Thumbnail Generation**: Auto-generated JPEG previews from FITS data
- **ASTAP Platesolving**: CLI integration to determine missing RA/Dec coordinates
- **Theme Support**: Dark/Light/System themes persisted to localStorage
- **Settings Page**: Configure scan paths, equipment overrides, and ASTAP binary

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Health check and database path |
| `/api/v1/dashboard` | GET | Aggregated dashboard data |
| `/api/v1/search?q=...` | GET | Full-text search via FTS5 |
| `/api/v1/targets` | GET | List targets (paginated, searchable, filterable by type/constellation) |
| `/api/v1/targets/types` | GET | Distinct object types and constellations for filter dropdowns |
| `/api/v1/targets/{id}` | GET | Target details with session count and exposure totals |
| `/api/v1/targets/{id}/sessions` | GET | Sessions for a target (paginated) |
| `/api/v1/targets/{id}/thumbnails` | GET | Recent frame thumbnails for a target |
| `/api/v1/sessions` | GET | List sessions (paginated, filterable by status/dates) |
| `/api/v1/sessions/{id}` | GET | Session details |
| `/api/v1/sessions/{id}/stats` | GET | Aggregated stats (frames per type, exposure per filter) |
| `/api/v1/frames` | GET | List frames (paginated, filterable, optional `has_coordinates`) |
| `/api/v1/frames/{id}/thumbnail` | GET | JPEG thumbnail for a specific frame |
| `/api/v1/cameras` | GET | Camera catalog with usage stats |
| `/api/v1/telescopes` | GET | Telescope catalog with usage stats |
| `/api/v1/filters` | GET | Filter usage statistics |
| `/api/v1/stats` | GET | Database statistics |
| `/api/v1/scan` | POST | Start background FITS scan |
| `/api/v1/scan/status` | GET | Get scan progress |
| `/api/v1/platesolve` | POST | Start ASTAP platesolving on unplated frames |
| `/api/v1/platesolve/status` | GET | Get platesolve progress |
| `/api/v1/settings` | GET/POST | Application settings (key/value) |

## Supported FITS Formats

- Standard FITS (.fit, .fits)
- Gzip-compressed FITS (.fit.gz, .fits.gz) — SGP format
- Extension headers: Reads HDU[1] for compressed files
- Coordinate formats: Numeric RA/DEC + HMS/DMS strings

## Known Issues / Limitations

- XISF files are detected but not yet parsed (skipped with warning)
- Session grouping by path may split multi-night observations of the same target
- HMS/DMS parsing covers common formats but not all edge cases

## Development

```bash
# Run tests
pytest tests/ -v -k "not integration"

# Run integration tests (requires astro data directory)
pytest tests/ -v -k "integration"

# Lint + type check
ruff check src/
mypy src/

# Frontend development
cd frontend-vue && npm run dev
```

## License

AGPL-3.0 — Network copyleft. If you run a modified version as a service, you must make the source available.

## Roadmap

See [docs/roadmap.md](docs/roadmap.md) for detailed development milestones.

- [x] ASTAP platesolving for frames missing coordinates
- [ ] Siril `.sss` script generator for processing pipelines
- [ ] XISF file parsing
- [ ] Quality metrics (FWHM, eccentricity) from Siril/Astap
- [ ] Processing pipeline integration
- [ ] Docker Compose deployment
