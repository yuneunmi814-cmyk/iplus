//! Lifecycle management for the iPlus local engine (FastAPI) sidecar.
//! Blueprint §3 pattern: target-triple path resolution -> spawn -> health poll -> cleanup.
//! Unlike Meetily's stdin/stdout pipe, iPlus talks to the engine over localhost HTTP.

use std::sync::Mutex;
use std::time::{Duration, Instant};

use tauri::{AppHandle, Manager};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

pub const ENGINE_PORT: u16 = 8787;
pub const HEALTH_URL: &str = "http://127.0.0.1:8787/health";

/// Holds the live engine child handle (so we can kill it on exit).
#[derive(Default)]
pub struct EngineProcess(pub Mutex<Option<CommandChild>>);

/// Spawn the engine sidecar and wait for health.
pub async fn spawn_engine(app: &AppHandle) -> anyhow::Result<()> {
    // Local SQLite path: $APPDATA/iplus.db
    let db_path = app
        .path()
        .app_data_dir()
        .map(|d| d.join("iplus.db"))
        .unwrap_or_else(|_| std::path::PathBuf::from("iplus.db"));
    if let Some(parent) = db_path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }

    // tauri-plugin-shell sidecar API — matches externalBin "binaries/iplus-engine".
    // Tauri bundles the binary with a target-triple suffix and resolves it at runtime.
    let (mut rx, child) = app
        .shell()
        .sidecar("iplus-engine")?
        .args([
            "--port",
            &ENGINE_PORT.to_string(),
            "--db",
            &db_path.to_string_lossy(),
            // Pass the shell PID so the engine self-terminates if the shell dies
            // (orphan prevention). PyInstaller's 2-process tree makes ppid checks insufficient.
            "--parent-pid",
            &std::process::id().to_string(),
        ])
        .spawn()?;

    // Keep the child handle
    app.state::<EngineProcess>()
        .0
        .lock()
        .unwrap()
        .replace(child);

    // Pipe stdout/stderr to the log
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    log::info!("[engine] {}", String::from_utf8_lossy(&line))
                }
                CommandEvent::Stderr(line) => {
                    log::warn!("[engine] {}", String::from_utf8_lossy(&line))
                }
                CommandEvent::Terminated(payload) => {
                    log::error!("[engine] terminated: {:?}", payload.code)
                }
                _ => {}
            }
        }
    });

    wait_for_health(HEALTH_URL, 30).await
}

/// Poll /health until it returns 200 (generous timeout for PyInstaller --onefile cold start).
pub async fn wait_for_health(url: &str, timeout_secs: u64) -> anyhow::Result<()> {
    let deadline = Instant::now() + Duration::from_secs(timeout_secs);
    let client = reqwest::Client::new();
    loop {
        let ok = client
            .get(url)
            .send()
            .await
            .map(|r| r.status().is_success())
            .unwrap_or(false);
        if ok {
            log::info!("engine healthy at {url}");
            return Ok(());
        }
        if Instant::now() > deadline {
            anyhow::bail!("engine health check timed out after {timeout_secs}s");
        }
        tokio::time::sleep(Duration::from_millis(400)).await;
    }
}

/// Clean up the sidecar on app exit — otherwise a zombie process holds the port (blueprint §3 gotcha).
pub fn shutdown_engine(app: &AppHandle) {
    if let Some(child) = app.state::<EngineProcess>().0.lock().unwrap().take() {
        log::info!("shutting down engine sidecar");
        let _ = child.kill();
    }
}
