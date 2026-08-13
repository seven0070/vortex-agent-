import { app, BrowserWindow, ipcMain, shell } from 'electron';
import { spawn, ChildProcess } from 'child_process';
import path from 'path';

let mainWindow: BrowserWindow | null = null;
let backendProcess: ChildProcess | null = null;

function startVortexBackend() {
  const pythonExecutable = process.platform === 'win32' ? 'python' : 'python3';
  // In production the backend lives two levels up from dist-electron/
  const serverScript = app.isPackaged
    ? path.join(process.resourcesPath, 'backend', 'main.py')
    // In dev, assumes the repo was cloned with the folder named 'vortex-agent-'
    // (the GitHub default). Adjust this path if your checkout differs.
    : path.join(__dirname, '../../vortex-agent/backend/main.py');

  backendProcess = spawn(pythonExecutable, [serverScript], {
    env: { ...process.env, PORT: '8000' },
    cwd: path.dirname(serverScript),
  });

  backendProcess.stdout?.on('data', (data) =>
    console.log(`[Backend]: ${data}`)
  );
  backendProcess.stderr?.on('data', (data) =>
    console.error(`[Backend Error]: ${data}`)
  );

  backendProcess.on('error', (err) =>
    console.error('[Backend] Failed to start:', err)
  );
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 900,
    minHeight: 600,
    titleBarStyle: 'hidden',
    trafficLightPosition: { x: 12, y: 12 },
    backgroundColor: '#18181b',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  // Load Vite dev server in development, built file in production
  const devServerUrl = process.env.VITE_DEV_SERVER_URL;
  if (devServerUrl) {
    mainWindow.loadURL(devServerUrl);
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  }
}

app.whenReady().then(() => {
  startVortexBackend();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

// Open external links in OS browser
ipcMain.on('open-external', (_event, url: string) => {
  shell.openExternal(url);
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('will-quit', () => {
  if (backendProcess) {
    backendProcess.kill();
    backendProcess = null;
  }
});
