# Vortex Desktop (Tauri 2 + React + TypeScript)

Vortex Desktop is a native shell UI layer over the existing `vortex-agent/backend` runtime.

## Architecture

- **Frontend:** React + TypeScript (`desktop/src`)
- **Native shell:** Tauri 2 (`desktop/src-tauri`)
- **Backend:** Python FastAPI in `vortex-agent/backend`
- **Connection:** local HTTP API (`127.0.0.1:8765`) started/stopped by Tauri lifecycle

## Screens

- Shell (window, sidebar, top bar, theme, route state)
- Chat
- Missions
- Council / Resolution / Memory / Knowledge Graph
- Governance / Sovereign / Tools
- Evolution
- Benchmarks / Observability
- Settings

## Development

```bash
cd desktop
npm install
npm run tauri:dev
```

## Frontend build validation

```bash
npm run typecheck
npm run build
```

## Native packaging

```bash
npm run tauri:build
```

The Tauri bundle includes backend resources from `../vortex-agent/backend/**`.
