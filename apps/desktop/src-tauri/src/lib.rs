mod sidecar;

use sidecar::{SidecarMutex, SidecarState};
use tauri::Manager;

/// 원격 서버 URL을 반환한다. 환경변수 PORR_SERVER_URL 또는 기본값.
#[tauri::command]
fn get_server_url() -> String {
    std::env::var("PORR_SERVER_URL")
        .unwrap_or_else(|_| "http://localhost:8010".to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(SidecarMutex::new(SidecarState::new()))
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_http::init())
        .invoke_handler(tauri::generate_handler![
            get_server_url,
            sidecar::start_sidecar,
            sidecar::stop_sidecar,
            sidecar::sidecar_status,
        ])
        .setup(|app| {
            #[cfg(debug_assertions)]
            {
                if let Some(window) = app.get_webview_window("main") {
                    window.open_devtools();
                }
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running PO,RR desktop app");
}
