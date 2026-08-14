use serde::Serialize;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use tauri::{AppHandle, Manager, State};

const BACKEND_PORT: u16 = 8765;

struct BackendState {
    child: Mutex<Option<Child>>,
}

#[derive(Serialize)]
struct LifecycleSnapshot {
    backend_running: bool,
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

fn spawn_backend(app: &AppHandle, state: &State<BackendState>) {
    if state.child.lock().ok().and_then(|c| c.as_ref().map(|_| ())).is_some() {
        return;
    }

    let candidates = backend_candidates(app);
    let target = candidates.into_iter().find(|path| path.exists());
    let Some(target) = target else {
        eprintln!("[vortex-desktop] no backend entrypoint found");
        return;
    };

    let child = if target
        .extension()
        .and_then(|ext| ext.to_str())
        .is_some_and(|ext| ext.eq_ignore_ascii_case("exe"))
    {
        Command::new(target)
            .env("PORT", BACKEND_PORT.to_string())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .ok()
    } else {
        let mut command = Command::new("python3");
        command
            .arg(target)
            .arg(BACKEND_PORT.to_string())
            .env("PORT", BACKEND_PORT.to_string())
            .stdout(Stdio::null())
            .stderr(Stdio::null());

        command.spawn().ok().or_else(|| {
            Command::new("python")
                .arg(target)
                .arg(BACKEND_PORT.to_string())
                .env("PORT", BACKEND_PORT.to_string())
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .spawn()
                .ok()
        })
    };

    if let Some(child) = child {
        if let Ok(mut lock) = state.child.lock() {
            *lock = Some(child);
        }
    }
}

fn stop_backend(state: &State<BackendState>) {
    if let Ok(mut lock) = state.child.lock() {
        if let Some(child) = lock.as_mut() {
            let _ = child.kill();
        }
        *lock = None;
    }
}

#[tauri::command]
fn get_backend_port() -> u16 {
    BACKEND_PORT
}

#[tauri::command]
fn lifecycle_snapshot(state: State<BackendState>) -> LifecycleSnapshot {
    let running = state
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
        .unwrap_or(false);

    LifecycleSnapshot {
        backend_running: running,
    }
}

pub fn run() {
    tauri::Builder::default()
        .manage(BackendState {
            child: Mutex::new(None),
        })
        .invoke_handler(tauri::generate_handler![get_backend_port, lifecycle_snapshot])
        .setup(|app| {
            let handle = app.handle().clone();
            let state: State<BackendState> = app.state();
            spawn_backend(&handle, &state);
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                let state: State<BackendState> = window.state();
                stop_backend(&state);
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
