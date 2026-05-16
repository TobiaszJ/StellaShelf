# frontend-vue

StellaShelf web frontend built with Vue 3, TypeScript, and Vite.

## Tech Stack

- **Vue 3** with Composition API and `<script setup>`
- **TypeScript** for type safety
- **Vite** for dev server and build
- **Pinia** for state management
- **Vue Router** for client-side routing
- **ECharts** (via vue-echarts) for data visualization
- **Lucide** for icons
- **Axios** for HTTP requests

## Development

```bash
cd frontend-vue
npm install
npm run dev      # Start dev server with hot-reload (proxies /api to localhost:8321)
npm run build    # Production build (output to dist/)
npm run preview  # Preview production build locally
```

## Views

| Route | View | Description |
|---|---|---|
| `/` | Dashboard | Stats, top targets, recent sessions, ECharts chart |
| `/targets` | Targets | Filterable/sortable target list with badges |
| `/targets/:id` | TargetDetail | Target info, thumbnails, session list |
| `/sessions` | Sessions | Filterable/sortable session list |
| `/sessions/:id` | SessionDetail | Frame list with pagination, filtering, aggregates |
| `/equipment` | Equipment | Cameras, telescopes, filters |
| `/search` | Search | FTS5 full-text search |
| `/scan` | Scan | Directory scanner with live progress |
| `/settings` | Settings | General config, equipment overrides |
| `/platesolve` | Platesolve | ASTAP platesolving runner |
| `/help` | Help | Documentation and shortcuts |

## Build Output

The production build outputs to `dist/`. The FastAPI backend serves the built SPA from `frontend-vue/dist/` when it exists.

```bash
npm run build
# Then start backend: stellashelf serve
```