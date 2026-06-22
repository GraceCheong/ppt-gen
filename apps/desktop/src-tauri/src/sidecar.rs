use std::sync::Mutex;
use tauri::AppHandle;
use tauri_plugin_shell::{process::CommandChild, ShellExt};

pub struct SidecarState {
    child: Option<CommandChild>,
    port: u16,
}

impl SidecarState {
    pub fn new() -> Self {
        Self { child: None, port: 8765 }
    }
}

impl Drop for SidecarState {
    fn drop(&mut self) {
        if let Some(child) = self.child.take() {
            let _ = child.kill();
        }
    }
}

pub type SidecarMutex = Mutex<SidecarState>;

#[derive(serde::Serialize)]
pub struct SidecarStatus {
    pub running: bool,
    pub port: u16,
    pub url: String,
}

/// 사이드카를 시작하고 URL을 반환한다. 이미 실행 중이면 기존 URL을 반환한다.
#[tauri::command]
pub async fn start_sidecar(
    app: AppHandle,
    state: tauri::State<'_, SidecarMutex>,
) -> Result<String, String> {
    // 이미 실행 중이면 즉시 반환
    let port = {
        let guard = state.lock().map_err(|e| e.to_string())?;
        if guard.child.is_some() {
            return Ok(format!("http://127.0.0.1:{}", guard.port));
        }
        guard.port
    };

    let sidecar = app
        .shell()
        .sidecar("porr-server")
        .map_err(|e| format!("사이드카 바이너리를 찾을 수 없습니다: {e}"))?
        .args(["--port", &port.to_string(), "--host", "127.0.0.1"]);

    let (mut rx, child) = sidecar
        .spawn()
        .map_err(|e| format!("사이드카 시작 실패: {e}"))?;

    {
        let mut guard = state.lock().map_err(|e| e.to_string())?;
        guard.child = Some(child);
    }

    // 사이드카 출력을 백그라운드에서 소비 (stdout/stderr 버퍼 차단 방지)
    tauri::async_runtime::spawn(async move {
        while let Some(_event) = rx.recv().await {}
    });

    Ok(format!("http://127.0.0.1:{port}"))
}

/// 사이드카를 종료한다.
#[tauri::command]
pub async fn stop_sidecar(state: tauri::State<'_, SidecarMutex>) -> Result<(), String> {
    let mut guard = state.lock().map_err(|e| e.to_string())?;
    if let Some(child) = guard.child.take() {
        child.kill().map_err(|e| e.to_string())?;
    }
    Ok(())
}

/// 사이드카 실행 상태를 반환한다.
#[tauri::command]
pub fn sidecar_status(state: tauri::State<'_, SidecarMutex>) -> SidecarStatus {
    // lock 실패 시 기본값 반환 (패닉 방지)
    match state.lock() {
        Ok(guard) => SidecarStatus {
            running: guard.child.is_some(),
            port: guard.port,
            url: format!("http://127.0.0.1:{}", guard.port),
        },
        Err(_) => SidecarStatus {
            running: false,
            port: 8765,
            url: "http://127.0.0.1:8765".to_string(),
        },
    }
}
