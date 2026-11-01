mod protocol;

use std::collections::HashMap;
use std::io::{BufRead, BufReader, Read};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};

use serde_json::{json, Value};
use tauri::{AppHandle, Manager, State};
use tauri_plugin_dialog::DialogExt;
use uuid::Uuid;

pub const ALLOWED_COMMANDS: &[&str] = &[
    "engine_health",
    "picker_open_folder",
    "picker_open_file",
    "datasets_open",
    "datasets_list_items",
    "datasets_work_status",
    "sessions_create",
    "sessions_get",
    "sessions_lock_roi",
    "sessions_propose",
    "sessions_select",
    "sessions_refine",
    "sessions_delete_prompt",
    "sessions_lock_region",
    "sessions_unlock_region",
    "sessions_start_next_region",
    "sessions_edit",
    "sessions_undo",
    "sessions_redo",
    "sessions_update_prompt",
    "sessions_qa",
    "drafts_inspect",
    "drafts_flush",
    "drafts_load",
    "drafts_discard",
    "labelme_preview",
    "labelme_export",
    "labelme_import",
    "labels_list",
    "labels_reclassify",
    "updates_info",
    "updates_verify",
    "sessions_begin_manual_empty",
    "sessions_expand_roi",
    "sessions_acknowledge_warning",
    "sessions_accept",
    "sessions_needs_review",
    "sessions_close",
    "jobs_cancel",
    "diagnostics_export",
    "engine_restart",
    "load_asset",
];

struct Grant {
    kind: String,
    path: String,
    display_name: String,
}

struct Inner {
    port: u16,
    secret: String,
    child: Option<Child>,
    grants: HashMap<String, Grant>,
}

pub struct AppState {
    inner: Mutex<Inner>,
}

fn repo_root() -> PathBuf {
    let manifest = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    manifest
        .parent()
        .and_then(Path::parent)
        .and_then(Path::parent)
        .map(Path::to_path_buf)
        .unwrap_or(manifest)
}

fn python_bin(root: &Path) -> PathBuf {
    let venv = root.join(".venv").join("Scripts").join("python.exe");
    if venv.exists() {
        venv
    } else {
        PathBuf::from("python")
    }
}

fn spawn_sidecar(secret: &str) -> Result<(Child, u16), String> {
    let root = repo_root();
    let python = python_bin(&root);
    let mut child = Command::new(&python)
        .args([
            "-m",
            "segvision.transport.desktop_api",
            "--secret",
            secret,
            "--port",
            "0",
            "--host",
            "127.0.0.1",
            "--prefer-real",
        ])
        .current_dir(&root)
        .env("CUDA_VISIBLE_DEVICES", "-1")
        .env("PYTHONPATH", root.join("src"))
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("spawn sidecar {}: {e}", python.display()))?;
    let stdout = child.stdout.take().ok_or("sidecar stdout missing")?;
    let mut reader = BufReader::new(stdout);
    let mut line = String::new();
    reader
        .read_line(&mut line)
        .map_err(|e| e.to_string())?;
    let info: Value = serde_json::from_str(line.trim()).map_err(|e| e.to_string())?;
    let port = info
        .get("port")
        .and_then(|v| v.as_u64())
        .ok_or("sidecar port missing")? as u16;
    // Keep reading stdout so the pipe does not fill.
    thread::spawn(move || {
        let mut buf = String::new();
        let _ = reader.read_to_string(&mut buf);
    });
    // A cold CPU-only MobileSAM load can legitimately take longer than the
    // fake sidecar. Keep the UI unopened until health is ready, but do not
    // misclassify model initialization as a crash.
    let deadline = Instant::now() + Duration::from_secs(60);
    let url = format!("http://127.0.0.1:{port}/v1/health");
    while Instant::now() < deadline {
        let client = reqwest::blocking::Client::new();
        if let Ok(resp) = client
            .get(&url)
            .header("X-SegVision-Launch-Secret", secret)
            .header("X-SegVision-Protocol-Version", protocol::PROTOCOL_VERSION)
            .send()
        {
            if resp.status().is_success() {
                return Ok((child, port));
            }
        }
        thread::sleep(Duration::from_millis(100));
    }
    let _ = child.kill();
    Err("sidecar health timeout".into())
}

fn proxy(
    state: &AppState,
    method: &str,
    path: &str,
    body: Option<Value>,
    extra: &[(&str, String)],
) -> Result<Value, String> {
    let (port, secret) = {
        let inner = state.inner.lock().map_err(|e| e.to_string())?;
        (inner.port, inner.secret.clone())
    };
    let url = format!("http://127.0.0.1:{port}{path}");
    let client = reqwest::blocking::Client::new();
    let mut req = match method {
        "GET" => client.get(&url),
        _ => client.post(&url),
    };
    req = req
        .header("X-SegVision-Launch-Secret", &secret)
        .header("X-SegVision-Protocol-Version", protocol::PROTOCOL_VERSION)
        .header("X-SegVision-Host-Proxy", "1");
    for (k, v) in extra {
        req = req.header(*k, v);
    }
    if let Some(body) = body {
        req = req.json(&body);
    }
    let resp = req.send().map_err(|e| e.to_string())?;
    let status = resp.status();
    let text = resp.text().map_err(|e| e.to_string())?;
    if !status.is_success() {
        return Err(text);
    }
    if text.is_empty() {
        return Ok(json!({}));
    }
    serde_json::from_str(&text).map_err(|e| e.to_string())
}

fn envelope(extra: Value) -> Value {
    let mut body = extra;
    if let Some(obj) = body.as_object_mut() {
        obj.entry("protocol_version")
            .or_insert_with(|| json!(protocol::PROTOCOL_VERSION));
        obj.entry("request_id")
            .or_insert_with(|| json!(Uuid::new_v4().to_string()));
    }
    body
}

fn asset_token_from_path(path: &str) -> Result<String, String> {
    let token = urlencoding::decode(path.trim_start_matches('/'))
        .map_err(|_| "asset token is not valid URL encoding")?
        .into_owned();
    if token.is_empty()
        || !token
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || byte == b'-' || byte == b'_')
    {
        return Err("asset token is invalid".into());
    }
    Ok(token)
}

fn asset_cors_origin(origin: Option<&str>) -> Option<&str> {
    match origin {
        Some(
            "tauri://localhost"
            | "http://tauri.localhost"
            | "https://tauri.localhost"
            | "http://localhost:5173"
            | "http://127.0.0.1:5173",
        ) => origin,
        _ => None,
    }
}

fn asset_response(
    status: u16,
    body: Vec<u8>,
    content_type: Option<&str>,
    cors_origin: Option<&str>,
) -> tauri::http::Response<Vec<u8>> {
    let mut builder = tauri::http::Response::builder().status(status);
    if let Some(content_type) = content_type {
        builder = builder.header("Content-Type", content_type);
    }
    if let Some(cors_origin) = cors_origin {
        builder = builder
            .header("Access-Control-Allow-Origin", cors_origin)
            .header("Vary", "Origin");
    }
    builder.body(body).unwrap()
}

#[tauri::command]
fn engine_health(state: State<AppState>) -> Result<Value, String> {
    proxy(&state, "GET", "/v1/health", None, &[])
}

#[tauri::command]
fn engine_restart(state: State<AppState>) -> Result<Value, String> {
    let old_child = {
        let mut inner = state.inner.lock().map_err(|e| e.to_string())?;
        inner.child.take()
    };
    if let Some(mut child) = old_child {
        let _ = child.kill();
        let _ = child.wait();
    }
    let secret = Uuid::new_v4().to_string();
    let (child, port) = spawn_sidecar(&secret)?;
    let mut inner = state.inner.lock().map_err(|e| e.to_string())?;
    inner.secret = secret;
    inner.port = port;
    inner.child = Some(child);
    Ok(json!({"state":"ready", "restarted":true, "protocol_version":protocol::PROTOCOL_VERSION}))
}

#[tauri::command]
fn picker_open_folder(app: AppHandle, state: State<AppState>, kind: String) -> Result<Value, String> {
    if !matches!(kind.as_str(), "dataset" | "output" | "checkpoint") {
        return Err(json!({"code":"grant_invalid","message":"unsupported grant kind"}).to_string());
    }
    let picked = app
        .dialog()
        .file()
        .blocking_pick_folder()
        .ok_or_else(|| json!({"code":"grant_invalid","message":"cancelled"}).to_string())?;
    let path = picked.into_path().map_err(|e| e.to_string())?;
    let grant_id = Uuid::new_v4().to_string();
    let display_name = path
        .file_name()
        .map(|s| s.to_string_lossy().into_owned())
        .unwrap_or_else(|| path.to_string_lossy().into_owned());
    let mut inner = state.inner.lock().map_err(|e| e.to_string())?;
    inner.grants.insert(
        grant_id.clone(),
        Grant {
            kind,
            path: path.to_string_lossy().into_owned(),
            display_name: display_name.clone(),
        },
    );
    Ok(json!({"grant_id": grant_id, "display_name": display_name}))
}

fn resolved_path(state: &AppState, grant_id: &str, expected_kind: &str) -> Result<String, String> {
    let inner = state.inner.lock().map_err(|e| e.to_string())?;
    let grant = inner
        .grants
        .get(grant_id)
        .ok_or_else(|| json!({"code":"grant_invalid","message":"unknown grant"}).to_string())?;
    if grant.kind != expected_kind {
        return Err(
            json!({"code":"grant_invalid","message":format!("expected {expected_kind} grant")})
                .to_string(),
        );
    }
    Ok(grant.path.clone())
}

fn output_headers(
    state: &AppState,
    output_grant_id: Option<&str>,
    required: bool,
) -> Result<Vec<(&'static str, String)>, String> {
    let Some(grant_id) = output_grant_id else {
        if required {
            return Err(
                json!({"code":"grant_invalid","message":"an output folder grant is required"})
                    .to_string(),
            );
        }
        return Ok(Vec::new());
    };
    let path = resolved_path(state, grant_id, "output")?;
    Ok(vec![("X-SegVision-Output-Path", path)])
}

#[tauri::command]
fn datasets_open(state: State<AppState>, grant_id: String) -> Result<Value, String> {
    let path = resolved_path(&state, &grant_id, "dataset")?;
    let body = envelope(json!({"grant_id": grant_id, "base_revision": 0}));
    proxy(
        &state,
        "POST",
        "/v1/datasets/open",
        Some(body),
        &[("X-SegVision-Resolved-Path", path)],
    )
}

#[tauri::command]
fn datasets_list_items(state: State<AppState>, dataset_id: String) -> Result<Value, String> {
    proxy(
        &state,
        "GET",
        &format!("/v1/datasets/{dataset_id}/items"),
        None,
        &[],
    )
}

#[tauri::command]
fn datasets_work_status(state: State<AppState>, dataset_id: String) -> Result<Value, String> {
    proxy(
        &state,
        "GET",
        &format!("/v1/datasets/{dataset_id}/work-status"),
        None,
        &[],
    )
}

#[tauri::command]
fn sessions_create(
    state: State<AppState>,
    dataset_id: String,
    item_id: String,
    prototype_match: Option<bool>,
) -> Result<Value, String> {
    proxy(
        &state,
        "POST",
        "/v1/sessions",
        Some(envelope(json!({
            "dataset_id": dataset_id,
            "item_id": item_id,
            "base_revision": 0,
            "prototype_match": prototype_match.unwrap_or(false)
        }))),
        &[],
    )
}

#[tauri::command]
fn sessions_get(state: State<AppState>, session_id: String) -> Result<Value, String> {
    proxy(&state, "GET", &format!("/v1/sessions/{session_id}"), None, &[])
}

#[tauri::command]
fn sessions_lock_roi(
    state: State<AppState>,
    session_id: String,
    base_revision: i64,
    class_id: String,
    roi_xyxy: Vec<i64>,
    output_grant_id: Option<String>,
) -> Result<Value, String> {
    let headers = output_headers(&state, output_grant_id.as_deref(), false)?;
    proxy(
        &state,
        "POST",
        &format!("/v1/sessions/{session_id}/lock-roi"),
        Some(envelope(json!({
            "session_id": session_id,
            "base_revision": base_revision,
            "class_id": class_id,
            "roi_xyxy": roi_xyxy
        }))),
        &headers,
    )
}

#[tauri::command]
fn sessions_propose(
    state: State<AppState>,
    session_id: String,
    base_revision: i64,
) -> Result<Value, String> {
    proxy(
        &state,
        "POST",
        &format!("/v1/sessions/{session_id}/proposals"),
        Some(envelope(json!({
            "session_id": session_id,
            "base_revision": base_revision
        }))),
        &[],
    )
}

#[tauri::command]
fn sessions_select(
    state: State<AppState>,
    session_id: String,
    base_revision: i64,
    candidate_id: Option<String>,
) -> Result<Value, String> {
    proxy(
        &state,
        "POST",
        &format!("/v1/sessions/{session_id}/select"),
        Some(envelope(json!({
            "session_id": session_id,
            "base_revision": base_revision,
            "candidate_id": candidate_id
        }))),
        &[],
    )
}

#[tauri::command]
fn sessions_refine(
    state: State<AppState>,
    session_id: String,
    base_revision: i64,
    x: i64,
    y: i64,
    label: i64,
) -> Result<Value, String> {
    proxy(
        &state,
        "POST",
        &format!("/v1/sessions/{session_id}/refinements"),
        Some(envelope(json!({
            "session_id": session_id,
            "base_revision": base_revision,
            "x": x,
            "y": y,
            "label": label
        }))),
        &[],
    )
}

#[tauri::command]
fn sessions_delete_prompt(
    state: State<AppState>,
    session_id: String,
    base_revision: i64,
    prompt_id: String,
) -> Result<Value, String> {
    proxy(
        &state,
        "POST",
        &format!("/v1/sessions/{session_id}/prompts/delete"),
        Some(envelope(json!({
            "session_id": session_id,
            "base_revision": base_revision,
            "prompt_id": prompt_id
        }))),
        &[],
    )
}

#[tauri::command]
fn sessions_lock_region(
    state: State<AppState>,
    session_id: String,
    base_revision: i64,
    x: i64,
    y: i64,
    guard: Option<bool>,
) -> Result<Value, String> {
    proxy(
        &state,
        "POST",
        &format!("/v1/sessions/{session_id}/regions/lock"),
        Some(envelope(json!({
            "session_id": session_id,
            "base_revision": base_revision,
            "x": x,
            "y": y,
            "guard": guard.unwrap_or(true)
        }))),
        &[],
    )
}

#[tauri::command]
fn sessions_unlock_region(
    state: State<AppState>,
    session_id: String,
    base_revision: i64,
    region_id: Option<String>,
) -> Result<Value, String> {
    proxy(
        &state,
        "POST",
        &format!("/v1/sessions/{session_id}/regions/unlock"),
        Some(envelope(json!({
            "session_id": session_id,
            "base_revision": base_revision,
            "region_id": region_id
        }))),
        &[],
    )
}

#[tauri::command]
fn sessions_start_next_region(
    state: State<AppState>,
    session_id: String,
    base_revision: i64,
) -> Result<Value, String> {
    proxy(
        &state,
        "POST",
        &format!("/v1/sessions/{session_id}/regions/next"),
        Some(envelope(json!({
            "session_id": session_id,
            "base_revision": base_revision
        }))),
        &[],
    )
}

#[tauri::command]
fn sessions_edit(
    state: State<AppState>,
    session_id: String,
    base_revision: i64,
    operation: String,
    points: Option<Vec<Vec<i64>>>,
    radius: Option<i64>,
    clip_rect: Option<Vec<i64>>,
) -> Result<Value, String> {
    proxy(
        &state,
        "POST",
        &format!("/v1/sessions/{session_id}/edits"),
        Some(envelope(json!({
            "session_id": session_id,
            "base_revision": base_revision,
            "operation": operation,
            "points": points.unwrap_or_default(),
            "radius": radius.unwrap_or(0),
            "clip_rect": clip_rect
        }))),
        &[],
    )
}

#[tauri::command]
fn sessions_undo(state: State<AppState>, session_id: String, base_revision: i64) -> Result<Value, String> {
    proxy(
        &state,
        "POST",
        &format!("/v1/sessions/{session_id}/undo"),
        Some(envelope(json!({"session_id": session_id, "base_revision": base_revision}))),
        &[],
    )
}

#[tauri::command]
fn sessions_redo(state: State<AppState>, session_id: String, base_revision: i64) -> Result<Value, String> {
    proxy(
        &state,
        "POST",
        &format!("/v1/sessions/{session_id}/redo"),
        Some(envelope(json!({"session_id": session_id, "base_revision": base_revision}))),
        &[],
    )
}

#[tauri::command]
fn sessions_update_prompt(
    state: State<AppState>,
    session_id: String,
    base_revision: i64,
    prompt_id: String,
    x: Option<i64>,
    y: Option<i64>,
    label: Option<i64>,
) -> Result<Value, String> {
    proxy(
        &state,
        "POST",
        &format!("/v1/sessions/{session_id}/prompts/update"),
        Some(envelope(json!({
            "session_id": session_id,
            "base_revision": base_revision,
            "prompt_id": prompt_id,
            "x": x,
            "y": y,
            "label": label
        }))),
        &[],
    )
}

#[tauri::command]
fn sessions_qa(state: State<AppState>, session_id: String) -> Result<Value, String> {
    proxy(
        &state,
        "POST",
        &format!("/v1/sessions/{session_id}/qa"),
        Some(envelope(json!({"session_id": session_id}))),
        &[],
    )
}

#[tauri::command]
fn drafts_inspect(
    state: State<AppState>,
    dataset_id: String,
    item_id: String,
) -> Result<Value, String> {
    proxy(
        &state,
        "POST",
        "/v1/drafts/inspect",
        Some(envelope(json!({"dataset_id": dataset_id, "item_id": item_id}))),
        &[],
    )
}

#[tauri::command]
fn drafts_flush(
    state: State<AppState>,
    session_id: String,
    base_revision: i64,
) -> Result<Value, String> {
    proxy(
        &state,
        "POST",
        "/v1/drafts/flush",
        Some(envelope(json!({"session_id": session_id, "base_revision": base_revision}))),
        &[],
    )
}

#[tauri::command]
fn drafts_load(
    state: State<AppState>,
    dataset_id: String,
    item_id: String,
    draft_id: Option<String>,
    session_id: Option<String>,
) -> Result<Value, String> {
    proxy(
        &state,
        "POST",
        "/v1/drafts/load",
        Some(envelope(json!({
            "dataset_id": dataset_id,
            "item_id": item_id,
            "draft_id": draft_id,
            "session_id": session_id
        }))),
        &[],
    )
}

#[tauri::command]
fn drafts_discard(
    state: State<AppState>,
    dataset_id: String,
    item_id: String,
    draft_id: Option<String>,
) -> Result<Value, String> {
    proxy(
        &state,
        "POST",
        "/v1/drafts/discard",
        Some(envelope(json!({
            "dataset_id": dataset_id,
            "item_id": item_id,
            "draft_id": draft_id
        }))),
        &[],
    )
}

#[tauri::command]
fn labelme_preview(state: State<AppState>, session_id: String) -> Result<Value, String> {
    proxy(
        &state,
        "POST",
        "/v1/labelme/preview",
        Some(envelope(json!({"session_id": session_id}))),
        &[],
    )
}

#[tauri::command]
fn labelme_export(
    state: State<AppState>,
    session_id: String,
    output_grant_id: String,
    acknowledge_cleanup: Option<bool>,
) -> Result<Value, String> {
    let headers = output_headers(&state, Some(&output_grant_id), true)?;
    proxy(
        &state,
        "POST",
        "/v1/labelme/export",
        Some(envelope(json!({"session_id": session_id, "acknowledge_cleanup": acknowledge_cleanup.unwrap_or(false)}))),
        &headers,
    )
}

#[tauri::command]
fn labelme_import(
    state: State<AppState>,
    session_id: String,
    document: Value,
    label_mapping: Option<Value>,
    decision: Option<String>,
) -> Result<Value, String> {
    proxy(
        &state,
        "POST",
        "/v1/labelme/import",
        Some(envelope(json!({"session_id": session_id, "document": document, "label_mapping": label_mapping, "decision": decision}))),
        &[],
    )
}

#[tauri::command]
fn labels_list(state: State<AppState>, dataset_id: Option<String>) -> Result<Value, String> {
    let path = match dataset_id {
        Some(dataset_id) if !dataset_id.is_empty() => format!("/v1/labels?dataset_id={dataset_id}"),
        _ => "/v1/labels".to_owned(),
    };
    proxy(&state, "GET", &path, None, &[])
}

#[tauri::command]
fn labels_reclassify(
    state: State<AppState>,
    session_id: String,
    base_revision: i64,
    class_id: String,
) -> Result<Value, String> {
    proxy(
        &state,
        "POST",
        &format!("/v1/sessions/{session_id}/reclassify"),
        Some(envelope(json!({
            "session_id": session_id,
            "base_revision": base_revision,
            "class_id": class_id
        }))),
        &[],
    )
}

#[tauri::command]
fn updates_info(state: State<AppState>) -> Result<Value, String> {
    proxy(&state, "GET", "/v1/updates/info", None, &[])
}

#[tauri::command]
fn updates_verify(state: State<AppState>, package_path: String) -> Result<Value, String> {
    proxy(
        &state,
        "POST",
        "/v1/updates/verify",
        Some(envelope(json!({"package_path": package_path}))),
        &[],
    )
}

#[tauri::command]
fn sessions_begin_manual_empty(
    state: State<AppState>,
    session_id: String,
    base_revision: i64,
    roi_xyxy: Option<Vec<i64>>,
) -> Result<Value, String> {
    proxy(
        &state,
        "POST",
        &format!("/v1/sessions/{session_id}/manual-empty"),
        Some(envelope(json!({
            "session_id": session_id,
            "base_revision": base_revision,
            "roi_xyxy": roi_xyxy
        }))),
        &[],
    )
}

#[tauri::command]
fn sessions_expand_roi(
    state: State<AppState>,
    session_id: String,
    base_revision: i64,
) -> Result<Value, String> {
    proxy(
        &state,
        "POST",
        &format!("/v1/sessions/{session_id}/expand-roi"),
        Some(envelope(json!({"session_id": session_id, "base_revision": base_revision}))),
        &[],
    )
}

#[tauri::command]
fn sessions_accept(
    state: State<AppState>,
    session_id: String,
    base_revision: i64,
    acknowledge_warnings: Vec<String>,
    output_grant_id: String,
    fit_prototype: Option<bool>,
) -> Result<Value, String> {
    let headers = output_headers(&state, Some(&output_grant_id), true)?;
    proxy(
        &state,
        "POST",
        &format!("/v1/sessions/{session_id}/accept"),
        Some(envelope(json!({
            "session_id": session_id,
            "base_revision": base_revision,
            "acknowledge_warnings": acknowledge_warnings,
            "fit_prototype": fit_prototype.unwrap_or(false)
        }))),
        &headers,
    )
}

#[tauri::command]
fn sessions_needs_review(
    state: State<AppState>,
    session_id: String,
    base_revision: i64,
    reason: String,
    output_grant_id: String,
) -> Result<Value, String> {
    let headers = output_headers(&state, Some(&output_grant_id), true)?;
    proxy(
        &state,
        "POST",
        &format!("/v1/sessions/{session_id}/needs-review"),
        Some(envelope(json!({
            "session_id": session_id,
            "base_revision": base_revision,
            "reason": reason
        }))),
        &headers,
    )
}

#[tauri::command]
fn sessions_close(state: State<AppState>, session_id: String, base_revision: i64) -> Result<Value, String> {
    proxy(
        &state,
        "POST",
        &format!("/v1/sessions/{session_id}/close"),
        Some(envelope(json!({"session_id": session_id, "base_revision": base_revision}))),
        &[],
    )
}

#[tauri::command]
fn jobs_cancel(state: State<AppState>, session_id: String, job_id: String) -> Result<Value, String> {
    proxy(
        &state,
        "POST",
        &format!("/v1/jobs/{job_id}/cancel"),
        Some(envelope(json!({"session_id": session_id, "job_id": job_id}))),
        &[],
    )
}

fn asset_data_url(mime: &str, bytes: &[u8]) -> String {
    const ALPH: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut out = String::from("data:");
    out.push_str(mime);
    out.push_str(";base64,");
    let mut i = 0;
    while i < bytes.len() {
        let b0 = bytes[i];
        let b1 = if i + 1 < bytes.len() { bytes[i + 1] } else { 0 };
        let b2 = if i + 2 < bytes.len() { bytes[i + 2] } else { 0 };
        let n = (u32::from(b0) << 16) | (u32::from(b1) << 8) | u32::from(b2);
        out.push(ALPH[((n >> 18) & 63) as usize] as char);
        out.push(ALPH[((n >> 12) & 63) as usize] as char);
        out.push(if i + 1 < bytes.len() {
            ALPH[((n >> 6) & 63) as usize] as char
        } else {
            '='
        });
        out.push(if i + 2 < bytes.len() {
            ALPH[(n & 63) as usize] as char
        } else {
            '='
        });
        i += 3;
    }
    out
}

#[tauri::command]
fn load_asset(state: State<AppState>, token: String) -> Result<Value, String> {
    if token.is_empty()
        || !token
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || byte == b'-' || byte == b'_')
    {
        return Err(json!({"code":"validation_failed","message":"asset token is invalid"}).to_string());
    }
    let (port, secret) = {
        let inner = state.inner.lock().map_err(|e| e.to_string())?;
        (inner.port, inner.secret.clone())
    };
    let url = format!(
        "http://127.0.0.1:{port}/v1/assets/{token}",
        token = urlencoding::encode(&token)
    );
    let client = reqwest::blocking::Client::new();
    let resp = client
        .get(url)
        .header("X-SegVision-Launch-Secret", secret)
        .header("X-SegVision-Protocol-Version", protocol::PROTOCOL_VERSION)
        .send()
        .map_err(|e| json!({"code":"not_found","message":e.to_string()}).to_string())?;
    if !resp.status().is_success() {
        return Err(json!({"code":"not_found","message":"asset token expired or unknown"}).to_string());
    }
    let mime = resp
        .headers()
        .get(reqwest::header::CONTENT_TYPE)
        .and_then(|v| v.to_str().ok())
        .unwrap_or("image/png")
        .to_string();
    let bytes = resp
        .bytes()
        .map_err(|e| json!({"code":"not_found","message":e.to_string()}).to_string())?;
    Ok(json!({"mime": mime, "data_url": asset_data_url(&mime, &bytes)}))
}

#[tauri::command]
fn diagnostics_export(state: State<AppState>) -> Result<Value, String> {
    let inner = state.inner.lock().map_err(|e| e.to_string())?;
    Ok(json!({"engine": "sidecar", "port_redacted": true, "secret_redacted": true, "has_child": inner.child.is_some()}))
}

pub fn run() {
    let _frozen = (protocol::OPERATIONS, protocol::ERROR_CODES, protocol::EVENT_KINDS);
    let _ = _frozen;
    let secret = Uuid::new_v4().to_string();
    let (child, port) = spawn_sidecar(&secret).expect("sidecar");
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(AppState {
            inner: Mutex::new(Inner {
                port,
                secret,
                child: Some(child),
                grants: HashMap::new(),
            }),
        })
        .invoke_handler(tauri::generate_handler![
            engine_health,
            picker_open_folder,
            datasets_open,
            datasets_list_items,
            datasets_work_status,
            sessions_create,
            sessions_get,
            sessions_lock_roi,
            sessions_propose,
            sessions_select,
            sessions_refine,
            sessions_delete_prompt,
            sessions_lock_region,
            sessions_unlock_region,
            sessions_start_next_region,
            sessions_edit,
            sessions_undo,
            sessions_redo,
            sessions_update_prompt,
            sessions_qa,
            drafts_inspect,
            drafts_flush,
            drafts_load,
            drafts_discard,
            labelme_preview,
            labelme_export,
            labelme_import,
            labels_list,
            labels_reclassify,
            updates_info,
            updates_verify,
            sessions_begin_manual_empty,
            sessions_expand_roi,
            sessions_accept,
            sessions_needs_review,
            sessions_close,
            jobs_cancel,
            engine_restart,
            diagnostics_export,
            load_asset
        ])
        .register_asynchronous_uri_scheme_protocol("segvision-asset", |ctx, request, responder| {
            let state = ctx.app_handle().state::<AppState>();
            let cors_origin = asset_cors_origin(
                request
                    .headers()
                    .get("origin")
                    .and_then(|value| value.to_str().ok()),
            )
            .map(str::to_owned);
            let token = match asset_token_from_path(request.uri().path()) {
                Ok(token) => token,
                Err(_) => {
                    responder.respond(asset_response(400, Vec::new(), None, cors_origin.as_deref()));
                    return;
                }
            };
            let (port, secret) = {
                let inner = state.inner.lock().unwrap();
                (inner.port, inner.secret.clone())
            };
            thread::spawn(move || {
                let url = format!("http://127.0.0.1:{port}/v1/assets/{token}");
                let client = reqwest::blocking::Client::new();
                match client
                    .get(url)
                    .header("X-SegVision-Launch-Secret", secret)
                    .header("X-SegVision-Protocol-Version", protocol::PROTOCOL_VERSION)
                    .send()
                {
                    Ok(resp) => {
                        let status = resp.status().as_u16();
                        let mime = resp
                            .headers()
                            .get(reqwest::header::CONTENT_TYPE)
                            .and_then(|v| v.to_str().ok())
                            .unwrap_or("application/octet-stream")
                            .to_string();
                        let bytes = if (200..300).contains(&status) {
                            resp.bytes().unwrap_or_default().to_vec()
                        } else {
                            Vec::new()
                        };
                        responder.respond(asset_response(
                            status,
                            bytes,
                            Some(&mime),
                            cors_origin.as_deref(),
                        ));
                    }
                    Err(_) => {
                        responder.respond(asset_response(
                            404,
                            Vec::new(),
                            None,
                            cors_origin.as_deref(),
                        ));
                    }
                }
            });
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                if let Ok(mut inner) = window.state::<AppState>().inner.lock() {
                    if let Some(child) = inner.child.as_mut() {
                        let _ = child.kill();
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running SegVision");
}

#[cfg(test)]
mod tests {
    use super::{asset_cors_origin, asset_token_from_path};

    #[test]
    fn asset_uri_path_uses_an_opaque_token() {
        assert_eq!(
            asset_token_from_path("/abc_DEF-123"),
            Ok("abc_DEF-123".to_owned())
        );
    }

    #[test]
    fn asset_uri_path_rejects_paths_and_empty_values() {
        for path in ["/", "/..", "/file%3Asecret", "/C%3A%5Csecret", "/a/b"] {
            assert!(asset_token_from_path(path).is_err(), "{path} should be rejected");
        }
    }

    #[test]
    fn asset_uri_allows_only_known_webview_origins_for_cors() {
        assert_eq!(
            asset_cors_origin(Some("http://tauri.localhost")),
            Some("http://tauri.localhost")
        );
        assert_eq!(
            asset_cors_origin(Some("http://localhost:5173")),
            Some("http://localhost:5173")
        );
        assert_eq!(asset_cors_origin(Some("https://example.test")), None);
    }
}
