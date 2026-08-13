import { app, BrowserWindow } from 'electron';
import { ChildProcess, spawn } from 'child_process';
import path from 'path';
import fs from 'fs';

const BACKEND_PORT = '8000';
let mainWindow: BrowserWindow | null = null;
let backendProcess: ChildProcess | null = null;

function backendPaths(): string[] {
  if (app.isPackaged) {
    const backendDir = path.join(process.resourcesPath, 'backend');
    const windowsExe = path.join(backendDir, 'main.exe');
    const pyScript = path.join(backendDir, 'main.py');
    return [windowsExe, pyScript];
  }

  const pyScript = path.resolve(__dirname, '../../vortex-agent/backend/main.py');
  return [pyScript];
}

function startVortexBackend(): void {
  const paths = backendPaths();
  const target = paths.find((candidate) => fs.existsSync(candidate));

  if (!target) {
    console.error('[Backend] No backend entrypoint found. Checked:', paths);
    return;
  }

  const isExe = target.endsWith('.exe');
  const pythonExecutables = process.platform === 'win32' ? ['python', 'python3'] : ['python3', 'python'];
  const args = isExe ? [] : [target, BACKEND_PORT];
  const env = { ...process.env, PORT: BACKEND_PORT, BACKEND_PORT };
  const attachLogListeners = (child: ChildProcess): void => {
    child.stdout?.on('data', (data) => {
      console.log(`[Backend] ${data.toString().trim()}`);
    });

    child.stderr?.on('data', (data) => {
      console.error(`[Backend Error] ${data.toString().trim()}`);
    });

    child.on('exit', (code, signal) => {
      console.log(`[Backend] exited (code=${code ?? 'null'}, signal=${signal ?? 'null'})`);
      if (backendProcess === child) {
        backendProcess = null;
      }
    });
  };

  const launch = (candidateIndex: number): void => {
    const command = isExe ? target : pythonExecutables[candidateIndex];
    const child = spawn(command, args, {
      env,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    backendProcess = child;
    attachLogListeners(child);

    child.on('error', (error: NodeJS.ErrnoException) => {
      const shouldRetry = !isExe && error.code === 'ENOENT' && candidateIndex < pythonExecutables.length - 1;
      if (shouldRetry) {
        launch(candidateIndex + 1);
        return;
      }
      console.error('[Backend] Failed to start backend process:', error.message);
    });
  };

  launch(0);
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1500,
    height: 920,
    minWidth: 1100,
    minHeight: 700,
    backgroundColor: '#09090b',
    title: 'Vortex Agent Desktop',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  if (!app.isPackaged) {
    mainWindow.loadURL('http://localhost:5173').catch((error) => {
      console.error('[Electron] Failed loading Vite dev server:', error);
    });
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html')).catch((error) => {
      console.error('[Electron] Failed loading production index.html:', error);
    });
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function stopBackend(): void {
  if (!backendProcess) {
    return;
  }

  backendProcess.kill('SIGTERM');
  backendProcess = null;
}

app.whenReady().then(() => {
  startVortexBackend();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('before-quit', stopBackend);
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
