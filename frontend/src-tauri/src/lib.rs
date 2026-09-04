use std::process::Command as StdCommand;
use std::sync::Mutex;
use tauri::{Manager, RunEvent};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

// Held in Tauri's managed state so the sidecar can be explicitly killed on
// app exit, rather than relying on the OS to clean it up. Wrapped in
// Option so kill() can be called exactly once and leave a clean None
// behind (avoids a double-kill panic if exit fires more than once).
struct SidecarHandle(Mutex<Option<CommandChild>>);

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            let shell = app.shell();
            let sidecar_command = shell
                .sidecar("oc-ecv-backend")
                .expect("failed to create sidecar command for oc-ecv-backend");
            let (mut rx, child) = sidecar_command
                .spawn()
                .expect("failed to spawn oc-ecv-backend sidecar");

            app.manage(SidecarHandle(Mutex::new(Some(child))));

            // Day 44: pipe sidecar stdout/stderr into the Tauri dev console
            // rather than discarding it. Directly addresses carried-forward
            // issue #1 ("capture piped stdout/stderr at failure moment") —
            // this is now always-on, not something to add reactively if the
            // crash recurs.
            tauri::async_runtime::spawn(async move {
                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stdout(line) => {
                            println!("[oc-ecv-backend stdout] {}", String::from_utf8_lossy(&line));
                        }
                        CommandEvent::Stderr(line) => {
                            eprintln!("[oc-ecv-backend stderr] {}", String::from_utf8_lossy(&line));
                        }
                        CommandEvent::Terminated(payload) => {
                            eprintln!("[oc-ecv-backend] terminated: {:?}", payload);
                        }
                        _ => {}
                    }
                }
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![greet])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            // Day 44: explicit sidecar termination on app exit — Tauri does
            // NOT do this automatically for sidecar processes. Without this,
            // closing the app window (vs. pkill) orphans oc-ecv-backend,
            // which would silently corrupt any subsequent RSS-monitoring
            // session run without a manual pkill first.
            if let RunEvent::ExitRequested { .. } | RunEvent::Exit = event {
                if let Some(state) = app_handle.try_state::<SidecarHandle>() {
                    if let Ok(mut guard) = state.0.lock() {
                        if let Some(child) = guard.take() {
                            // Confirmed Day 44: child.kill() alone only
                            // terminates the PyInstaller bootloader PID,
                            // leaving the double-forked worker process
                            // orphaned and holding significant RSS (~138MB
                            // observed). pkill -P <bootloader_pid> kills the
                            // worker (the bootloader's child) FIRST, then
                            // child.kill() cleans up the bootloader itself.
                            let bootloader_pid = child.pid();
                            let pkill_result = StdCommand::new("pkill")
                                .arg("-P")
                                .arg(bootloader_pid.to_string())
                                .status();
                            if let Err(e) = pkill_result {
                                eprintln!(
                                    "[oc-ecv-backend] pkill -P {} failed to run: {}",
                                    bootloader_pid, e
                                );
                            }
                            let _ = child.kill();
                        }
                    }
                }
            }
        });
}