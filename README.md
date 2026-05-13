# StellaShelf

**Astrophotography Digital Asset Manager & Processing Hub**

StellaShelf is a web-based tool for organizing, cataloging, and processing deep-sky astrophotography data. It scans FITS/XISF files, extracts metadata from headers, auto-groups sessions by object/date/equipment, and generates Siril processing pipelines.

## Features

- 🔭 **Auto-discovery** — Recursively scans your astro data directory, reads FITS/XISF headers
- 📋 **Smart grouping** — Automatically groups frames into sessions by object, date, camera, telescope, and filter
- 🔍 **Full-text search** — Find any object, session, or frame instantly
- 📊 **Dashboard** — Total exposure time, session counts, equipment overview
- 🖥️ **Processing pipelines** — Generate Siril CLI scripts from sessions with one click
- 🎛️ **Equipment catalog** — Auto-detected cameras, telescopes, and filters from your data

## Architecture

```
Browser (Vue 3 + Vite)
    ↕ REST API + WebSocket
FastAPI Backend (Python)
    ↕
SQLite + FTS5
    ↕
FITS/XISF Scanner (astropy) + ASTAP (platesolver)
```

## Data Structure Support

StellaShelf understands the common astrophotography folder layout:

```
Camera/
  ├── master calibration files (darks, bias, flats)
  └── Telescope/
      └── Object/
          └── Date/
              └── Light frames
```

It also reads metadata from Sequence Generator Pro, N.I.N.A., Ekos/INDI, and other capture software headers.

## Quick Start

```bash
# Install dependencies
pip install -e ".[dev]"

# Run the scanner
stellashelf scan /path/to/astro/data

# Start the web UI
stellashelf serve
```

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, branch conventions, and commit guidelines.

## License

AGPL-3.0 — See [LICENSE](LICENSE) for details. Commercial licensing available on request.