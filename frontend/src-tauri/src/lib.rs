use tauri_plugin_shell::ShellExt;

// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/
#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            let shell = app.shell();
            let sidecar_command = shell
                .sidecar("oc-ecv-backend")
                .expect("failed to create sidecar command for oc-ecv-backend");
            let (mut _rx, _child) = sidecar_command
                .spawn()
                .expect("failed to spawn oc-ecv-backend sidecar");
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![greet])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}