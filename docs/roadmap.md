# Roadmap

## Current Status: Foundation Complete ✅

The core scanning, database, and API infrastructure is operational. The Vue 3 frontend provides a modern browsing experience.

## Upcoming Milestones

### Milestone 3 — Browse & Search Enhancements (Week 5-6)

- [ ] Targets overview: filterable/sortable table with badges
- [ ] Session detail view: frame list, calibration status, exposure totals
- [ ] Equipment catalog: cameras, telescopes, filters
- [ ] Full-text search across all metadata
- [ ] Dashboard: stats (total objects, sessions, exposure hours, storage)
- [ ] Thumbnail generation for sample frames

### Milestone 4 — Pipeline Integration (Week 7-8)

> Siril integration

- [ ] Siril script generator (.sss) per session
- [ ] Pipeline configuration: calibration → registration → stacking → PCC
- [ ] Remote execution via SSH to workstation
- [ ] Pipeline status tracking via WebSocket
- [ ] Result preview (stacked image thumbnail)

### Milestone 5 — Polish & Release (Week 9-10)

- [ ] Settings page (paths, equipment overrides)
- [ ] Dark mode
- [ ] Performance optimization (large collections 10k+)
- [ ] ASTAP platesolving for unidentified objects
- [ ] RAW format support (CR2, NEF, ARW)
- [ ] Docker deployment configuration
- [ ] Documentation site / User guide