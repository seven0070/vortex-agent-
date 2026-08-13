# Vortex Agent Desktop (Electron + React)

Professional 3-pane desktop workspace for local Vortex Agent usage on Windows.

## Features

- **Left pane**: sidebar tabs for Files, Skills, and Memory
- **Middle pane**: code/diff viewer with **Accept/Reject** actions and floating command bar
- **Right pane**: live tool execution stream with command status + output
- Electron main process auto-starts `vortex-agent/backend/main.py` on port **8000**
- Graceful backend shutdown when Electron exits
- Works in development and production packaging modes

## Setup

From repository root:

```bash
cd /home/runner/work/vortex-agent-/vortex-agent-/desktop
npm install --legacy-peer-deps
```

## Development

```bash
npm run electron:dev
```

This starts:

- Vite dev server for React hot reload
- TypeScript watch for Electron main/preload files
- Electron desktop shell

## Production Build (Windows)

```bash
npm run build
```

Build artifacts are created under `desktop/release/` and include a Windows installer (`.exe`) via `electron-builder`.

## Backend Packaging Notes

`electron-builder.yml` includes `../vortex-agent/backend` under `extraResources`. If you bundle a PyInstaller executable later (for example `main.exe`), Electron will automatically prefer it over `main.py` in packaged mode.
