use serde::Serialize;
use std::io::{Read, Write};
use std::net::TcpStream;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::Duration;
use tauri::{AppHandle, Manager, State};

const BACKEND_PORT: u16 = 8765;

struct BackendState {
    child: Mutex<Option<Child>>,
    last_error: Mutex<Option<String>>,
}

impl Drop for BackendState {
    fn drop(&mut self) {
        if let Ok(mut lock) = self.child.lock() {
            if let Some(child) = lock.as_mut() {
                let _ = child.kill();
                let _ = child.wait();
            }
            *lock = None;
        }
    }
}

#[derive(Serialize)]
struct LifecycleSnapshot {
    backend_running: bool,
    backend_port: u16,
    last_error: Option<String>,
}

fn backend_candidates(app: &AppHandle) -> Vec<PathBuf> {
    let mut candidates = vec![];

    if cfg!(debug_assertions) {
        let dev_path = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../vortex-agent/backend/main.py");
        candidates.push(dev_path);
    }

    if let Ok(resource) = app.path().resource_dir() {
        candidates.push(resource.join("vortex-backend/main.py"));
        candidates.push(resource.join("vortex-backend/main.exe"));
    }

    candidates
}

fn running_child(state: &State<BackendState>) -> bool {
    state
        .child
        .lock()
        .ok()
        .map(|mut child| {
            if let Some(process) = child.as_mut() {
                process.try_wait().ok().flatten().is_none()
            } else {
                false
            }
        })
        .unwrap_or(false)
}

fn spawn_backend(app: &AppHandle, state: &State<BackendState>) -> Result<(), String> {
    if running_child(state) {
        return Ok(());
    }

    let candidates = backend_candidates(app);
    let target = candidates.into_iter().find(|path| path.exists());
    let Some(target) = target else {
        let error = "No backend entrypoint found".to_string();
        if let Ok(mut lock) = state.last_error.lock() {
            *lock = Some(error.clone());
        }
        return Err(error);
    };

    let child = if target
        .extension()
        .and_then(|ext| ext.to_str())
        .is_some_and(|ext| ext.eq_ignore_ascii_case("exe"))
    {
        Command::new(target)
            .env("PORT", BACKEND_PORT.to_string())
            .stdout(Stdio::inherit())
            .stderr(Stdio::inherit())
            .spawn()
            .ok()
    } else {
        let mut command = Command::new("python3");
        command
            .arg(target.clone())
            .arg(BACKEND_PORT.to_string())
            .env("PORT", BACKEND_PORT.to_string())
            .stdout(Stdio::inherit())
            .stderr(Stdio::inherit());

        command.spawn().ok().or_else(|| {
            Command::new("python")
                .arg(target)
                .arg(BACKEND_PORT.to_string())
                .env("PORT", BACKEND_PORT.to_string())
                .stdout(Stdio::inherit())
                .stderr(Stdio::inherit())
                .spawn()
                .ok()
        })
    };

    if let Some(child) = child {
        if let Ok(mut lock) = state.child.lock() {
            *lock = Some(child);
        }
        if let Ok(mut lock) = state.last_error.lock() {
            *lock = None;
        }
        Ok(())
    } else {
        let error = "Failed to spawn backend process".to_string();
        if let Ok(mut lock) = state.last_error.lock() {
            *lock = Some(error.clone());
        }
        Err(error)
    }
}

fn request_shutdown() -> bool {
    let mut stream = match TcpStream::connect(("127.0.0.1", BACKEND_PORT)) {
        Ok(stream) => stream,
        Err(_) => return false,
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(1200)));
    let _ = stream.set_write_timeout(Some(Duration::from_millis(1200)));
    let request = b"POST /api/runtime/shutdown HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\nContent-Length: 0\r\n\r\n";
    if stream.write_all(request).is_err() {
        return false;
    }
    let mut buffer = [0_u8; 256];
    let _ = stream.read(&mut buffer);
    true
}

fn stop_backend_internal(state: &State<BackendState>) {
    let _ = request_shutdown();
    thread::sleep(Duration::from_millis(200));

    if let Ok(mut lock) = state.child.lock() {
        if let Some(child) = lock.as_mut() {
            for _ in 0..16 {
                if child.try_wait().ok().flatten().is_some() {
                    break;
                }
                thread::sleep(Duration::from_millis(250));
            }
            if child.try_wait().ok().flatten().is_none() {
                let _ = child.kill();
                let _ = child.wait();
            }
        }
        *lock = None;
    }
}

#[tauri::command]
fn start_backend(app: AppHandle, state: State<BackendState>) -> Result<(), String> {
    spawn_backend(&app, &state)
}

#[tauri::command]
fn stop_backend(state: State<BackendState>) {
    stop_backend_internal(&state);
}

#[tauri::command]
fn restart_backend(app: AppHandle, state: State<BackendState>) -> Result<(), String> {
    stop_backend_internal(&state);
    spawn_backend(&app, &state)
}

#[tauri::command]
fn get_backend_port() -> u16 {
    BACKEND_PORT
}

#[tauri::command]
fn lifecycle_snapshot(state: State<BackendState>) -> LifecycleSnapshot {
    let running = running_child(&state);
    let last_error = state
        .last_error
        .lock()
        .ok()
        .and_then(|value| value.clone());

    LifecycleSnapshot {
        backend_running: running,
        backend_port: BACKEND_PORT,
        last_error,
    }
}

pub fn run() {
    tauri::Builder::default()
        .manage(BackendState {
            child: Mutex::new(None),
            last_error: Mutex::new(None),
        })
        .invoke_handler(tauri::generate_handler![
            get_backend_port,
            lifecycle_snapshot,
            start_backend,
            stop_backend,
            restart_backend
        ])
        .setup(|app| {
            let handle = app.handle().clone();
            let state: State<BackendState> = app.state();
            let _ = spawn_backend(&handle, &state);
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                let state: State<BackendState> = window.state();
                stop_backend_internal(&state);
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
