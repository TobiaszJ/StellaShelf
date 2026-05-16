# Roadmap

## Current Status: v0.3.0 — Name Normalization, Target Merge, DB Cleanup & Platesolving ✅

The core scanning, database, API infrastructure, and data management are operational. ASTAP platesolving is integrated and working with a 1.2 GB star database (D80). The Vue 3 frontend provides a modern browsing experience with 12 views, search, thumbnails, dark mode, and settings.

## Completed Milestones

### Milestone 1 — Core Infrastructure ✅

- [x] FITS header scanner with Met data extraction
- [x] SQLite + FTS5 database with SQLAlchemy ORM
- [x] Click CLI with scan, stats, and serve commands
- [x] FastAPI REST API (20+ endpoints)
- [x] Vue 3 SPA with Vite build pipeline

### Milestone 2 — Scanning & Data Import ✅

- [x] Recursive directory scanning
- [x] FITS header extraction with alias handling
- [x] Session grouping by target + date + equipment
- [x] Duplicate detection by filepath
- [x] Calibration file identification
- [x] Filename-based fallback parser
- [x] Path-based equipment extraction

### Milestone 3 — Browse & Search Enhancements ✅

- [x] Targets overview with filterable/sortable table and badges
- [x] Session detail view with frame list and per-filter aggregates
- [x] Equipment catalog (cameras, telescopes, filters)
- [x] Full-text search (FTS5-powered)
- [x] Dashboard with stats, top targets, recent sessions
- [x] Thumbnail generation (FITS → JPEG)

### Milestone 4 — Settings & Polish ✅

- [x] Settings page (paths, ASTAP binary, theme)
- [x] Dark mode (CSS variables, system preference, manual toggle)
- [x] ASTAP platesolving with background task, progress bar, log
- [x] Name normalization (M51, m51, M 51 → M 51)
- [x] Target merging (manual per-target + auto-merge-all-duplicates)
- [x] Duplicate detection with batch merge
- [x] Frame cleanup (search by filename/path, bulk delete)
- [x] Orphan cleanup (remove empty session/target/equipment)
- [x] Frame preview modal with scrollable FITS header
- [x] Sortable tables across all views

## Upcoming Milestones

### Milestone 5 — Pipeline Integration

> Siril integration

- [ ] Siril script generator (.sss) per session
- [ ] Pipeline configuration (calibration → registration → stacking → PCC)
- [ ] Remote execution via SSH to workstation
- [ ] Pipeline status tracking via WebSocket
- [ ] Result preview (stacked image thumbnail)

### Milestone 6 — Performance & Deployment

- [ ] Performance optimization for large collections (10k+)
- [ ] RAW format support (CR2, NEF, ARW)
- [ ] Docker deployment configuration

### Milestone 7 — Object Identification

- [x] OpenNGC catalog integration (NGC.csv + addendum.csv)
- [ ] FOV-based dominant object lookup (size-weighted)
- [ ] Background identify task with progress
- [ ] Auto-create targets from identified objects

## Ideenspeicher

> Ideen die zu einem späteren Zeitpunkt nützlich sein könnten, aber aktuell nicht priorisiert sind.

### SIMBAD TAP API als Fallback-Lookup
Falls der lokale NGC/IC-OpenNGC-Katalog kein passendes Objekt findet, könnte eine **SIMBAD TAP Cone-Search** (HTTP POST) als Online-Fallback dienen. SIMBAD sortiert nach `nbref DESC` (Anzahl wissenschaftlicher Referenzen), sodass das prominenteste Objekt im Suchfeld gefunden wird.

- Endpoint: `http://simbad.cds.unistra.fr/simbad/sim-tap/sync`
- Keine zusätzlichen Dependencies (stdlib `urllib` reicht)
- Ca. 50-300ms pro Query
- Rate-Limit: ~5-10 req/s
- Abdeckung: Millionen Objekte (nicht nur NGC/IC)
- Vorteil: Findet auch Sharpless, LDN, Barnard, etc.

Python-Beispiel:
```python
import urllib.request, urllib.parse, json
query = f"""SELECT TOP 1 main_id, ra, dec, otype, nbref,
DISTANCE(POINT('ICRS', ra, dec), POINT('ICRS', {ra_deg}, {dec_deg})) AS dist
FROM basic
WHERE CONTAINS(POINT('ICRS', ra, dec), CIRCLE('ICRS', {ra_deg}, {dec_deg}, 0.5))=1
ORDER BY nbref DESC"""
data = urllib.parse.urlencode({"REQUEST":"doQuery","LANG":"ADQL","FORMAT":"json","QUERY":query}).encode()
req = urllib.request.Request("http://simbad.cds.unistra.fr/simbad/sim-tap/sync", data=data)
with urllib.request.urlopen(req, timeout=15) as resp:
    result = json.loads(resp.read())
```
