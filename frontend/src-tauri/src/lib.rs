//! iPlus desktop app library entry. Spawns the engine sidecar in setup and cleans it
//! up on exit. The frontend talks to the engine on localhost:8787 over HTTP.

mod engine_sidecar;
use engine_sidecar::{shutdown_engine, spawn_engine, EngineProcess};
use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let mut builder = tauri::Builder::default();

    // Desktop single-instance guard (prevents engine port conflicts)
    #[cfg(desktop)]
    {
        builder = builder.plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            if let Some(w) = app.get_webview_window("main") {
                let _ = w.set_focus();
            }
        }));
    }

    builder
        .plugin(
            tauri_plugin_log::Builder::new()
                .level(log::LevelFilter::Info)
                .build(),
        )
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_store::Builder::new().build())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_notification::init())
        .manage(EngineProcess::default())
        .setup(|app| {
            let handle = app.handle().clone();
            // Spawn the engine sidecar (background, awaits health)
            tauri::async_runtime::spawn(async move {
                if let Err(e) = spawn_engine(&handle).await {
                    log::error!("failed to start engine: {e:#}");
                }
            });
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                shutdown_engine(&window.app_handle());
            }
        })
        .build(tauri::generate_context!())
        .expect("error while building iPlus")
        .run(|app_handle, event| {
            // Backstop: clean up the sidecar on any clean exit path (incl. Cmd-Q)
            if let tauri::RunEvent::Exit = event {
                shutdown_engine(app_handle);
            }
        });
}
