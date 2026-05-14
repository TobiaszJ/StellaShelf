# Roadmap

## Current Status: Browse & Search + Settings Complete ✅

The core scanning, database, and API infrastructure is operational. The Vue 3 frontend provides a modern browsing experience with 11 views, search, thumbnails, dark mode, and settings.

## Completed Milestones

### Milestone 3 — Browse & Search Enhancements ✅

- [x] Targets overview: filterable/sortable table with badges (object_type, constellation filters)
- [x] Session detail view: frame list with pagination, frame type filter, exposure per filter aggregates
- [x] Equipment catalog: cameras, telescopes, filters with sortable tabs and pagination
- [x] Full-text search across all metadata (FTS5-powered API + Search.vue)
- [x] Dashboard: stats, top targets, cameras, ECharts bar chart, recent sessions
- [x] Thumbnail generation for sample frames (FITS → JPEG, auto-generated after import)

### Milestone 4 — Settings & Polish ✅

- [x] Settings page (general config, equipment override names)
- [x] Dark mode (CSS variables, system preference auto-detect, manual toggle)
- [x] ASTAP platesolving for unidentified objects (CLI integration, API endpoint, Platesolve.vue)
- [x] Documentation site / User guide (Help.vue with formats, shortcuts, database info)

## Upcoming Milestones

### Milestone 5 — Pipeline Integration (Week 9-10)

> Siril integration

- [ ] Siril script generator (.sss) per session
- [ ] Pipeline configuration: calibration → registration → stacking → PCC
- [ ] Remote execution via SSH to workstation
- [ ] Pipeline status tracking via WebSocket
- [ ] Result preview (stacked image thumbnail)

### Milestone 6 — Performance & Deployment (Week 11-12)

- [ ] Performance optimization (large collections 10k+)
- [ ] RAW format support (CR2, NEF, ARW)
- [ ] Docker deployment configuration