# Vortex Agent Desktop

Electron + React desktop application for Vortex Agent with a 3-pane pro workspace layout and a Windows installer.

## Features

- **3-Pane Pro Workspace**
  - Left: File explorer / Skills / Memory tabs
  - Middle: Code/diff viewer with Accept & Reject buttons + floating command bar
  - Right: Live tool execution log
- **Windows Installer** — installs to Program Files, creates desktop & Start Menu shortcuts
- **Auto-spawns** the Vortex Agent Python backend on launch
- Dark zinc/indigo theme, Lucide icons, Tailwind CSS

---

## Prerequisites

| Requirement | Version |
|-------------|---------|
| Node.js | 18 LTS or later |
| npm | 9+ |
| Python | 3.10+ (must be on PATH as `python` on Windows) |

---

## Development Setup

```bash
# 1. Install dependencies
cd desktop
npm install

# 2. Start dev server (Vite + Electron with hot reload)
npm run electron:dev
```

The app opens automatically.  Backend starts at `http://localhost:8000`.

---

## Build Windows Installer

```bash
# Compiles TypeScript, bundles with Vite, then creates installer
npm run build
```

Output: **`dist/Vortex Agent Setup 1.0.0.exe`**

---

## Installation (End Users)

1. Download `Vortex Agent Setup 1.0.0.exe`
2. Double-click to run the installer
3. Follow the setup wizard (choose install directory, create shortcuts)
4. Launch **Vortex Agent** from the desktop or Start Menu

### Uninstall

Open **Settings → Apps → Vortex Agent → Uninstall**, or run the uninstaller from the Start Menu.

---

## Project Layout

```
desktop/
├── electron/
│   ├── main.ts         # Electron main process (spawns Python backend + window)
│   └── preload.ts      # Context bridge for IPC
├── src/
│   ├── components/
│   │   ├── Sidebar.tsx  # File explorer, Skills, Memory tabs
│   │   ├── Editor.tsx   # Code/diff viewer with Accept/Reject
│   │   └── Terminal.tsx # Live tool execution stream
│   ├── App.tsx          # 3-pane layout
│   ├── index.css        # Tailwind CSS
│   └── main.tsx         # React entry point
├── assets/
│   └── icon.ico         # App icon for installer
├── electron-builder.yml # Windows installer configuration
├── package.json
├── tsconfig.json
├── tsconfig.node.json
└── vite.config.ts
```

---

## Backend Integration

The desktop app communicates with the FastAPI backend over `http://localhost:8000`.

| Endpoint | Usage |
|----------|-------|
| `POST /api/chat` | Send a prompt to the agent |
| `GET /api/tools` | List available tools |
| `GET /api/memory` | Read agent memory |
| `GET /api/orchestration` | Orchestration status |

The Python process is spawned automatically by `electron/main.ts` using the system `python` (Windows) or `python3` (macOS/Linux).

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Backend won't start | Ensure Python is on PATH and `pip install -r requirements.txt` has been run inside `vortex-agent/backend/` |
| White screen on launch | Wait ~3 s for Vite dev server; or run `npm run dev` first |
| `electron-builder` fails | Install WiX Toolset 3.x for MSI, or use default NSIS |
| Port 8000 in use | Stop other services or change `PORT` env in `electron/main.ts` |

---

## Code Signing (Optional)

Set the following environment variables before running `npm run build` for a signed installer:

```bash
set CSC_LINK=path\to\certificate.pfx
set CSC_KEY_PASSWORD=your-password
```
