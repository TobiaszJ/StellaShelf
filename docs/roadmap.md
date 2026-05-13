# Roadmap

## Milestone 1 — Foundation (Week 1-2)

> Project skeleton, database schema, FITS scanner, API stub

- [ ] Project structure (Python package, pyproject.toml, dev dependencies)
- [ ] SQLite schema (targets, sessions, frames, equipment, FTS5 index)
- [ ] FITS header scanner (support compressed FITS from SGP)
- [ ] Filename-based fallback parser
- [ ] Auto-grouping logic (object + date + instrument + filter → session)
- [ ] CLI: `stellashelf scan <path>` with progress reporting
- [ ] FastAPI skeleton with /api/v1/ endpoints
- [ ] CI: GitHub Actions (lint, type-check, test)

## Milestone 2 — Scanner & Import (Week 3-4)

> Full scanner with web UI for import workflows

- [ ] Recursive directory scanner with progress tracking
- [ ] Import preview: detected metadata before committing
- [ ] Equipment auto-detection from headers (cameras, telescopes, filters)
- [ ] Calibration file detection (master darks, biases, flats)
- [ ] Web UI: Scan page with live progress
- [ ] Web UI: Import review with grouping suggestions

## Milestone 3 — Browse & Search (Week 5-6)

> Core browsing experience

- [ ] Targets overview: filterable/sortable table with badges
- [ ] Session detail view: frame list, calibration status, exposure totals
- [ ] Equipment catalog: cameras, telescopes, filters
- [ ] Full-text search across all metadata
- [ ] Dashboard: stats (total objects, sessions, exposure hours, storage)
- [ ] Thumbnail generation for sample frames

## Milestone 4 — Pipeline (Week 7-8)

> Siril integration

- [ ] Siril script generator (.sss) per session
- [ ] Pipeline configuration: calibration → registration → stacking → PCC
- [ ] Remote execution via SSH to workstation
- [ ] Pipeline status tracking via WebSocket
- [ ] Result preview (stacked image thumbnail)

## Milestone 5 — Polish & Release (Week 9-10)

- [ ] Settings page (paths, equipment overrides)
- [ ] Dark mode
- [ ] Performance optimization (large collections 10k+)
- [ ] ASTAP platesolving for unidentified objects
- [ ] RAW format support (CR2, NEF, ARW)
- [ ] Docker deployment configuration
- [ ] Documentation site / User guide