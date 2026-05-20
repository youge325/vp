//! Structured shell-side error type for Tauri commands.
//!
//! Replaces the legacy `Result<T, String>` convention with a typed enum that
//! maps to `protocol::TaskErrorCode`. The custom `Serialize` impl emits
//! `{ code, message }` so the frontend can route on `code` rather than parse
//! free-form strings.
//!
//! Phase C.2.3 removed the catch-all `Other(String)` / `From<String>` /
//! `From<&str>` variants. Any new failure must pick a named variant — pick
//! `BackendExit` for controller-internal panics, `Persistence` for storage
//! IO, etc. This keeps the wire-level `code` field meaningful for the
//! frontend.

use std::fmt;

use serde::{Serialize, Serializer};

use crate::protocol::TaskErrorCode;

#[derive(Debug)]
pub enum ShellError {
    RuntimeResolution(String),
    Spawn(std::io::Error),
    /// Phase 2.1 — CLI 成功退出(状态码 0)但未在 stdout 上输出有效 JSON。
    /// 原 ``BackendExit("Backend CLI did not emit JSON output.")`` 的语义
    /// 被提取为独立变体,避免与进程崩溃/信封错误混为一谈。
    BackendNoJson,
    /// Phase 2.1 — 后端返回了结构化的错误信封
    /// ``{"type":"error", code, message, details}``。
    /// 保留 code 字段,让前端可以直接按 ``TaskErrorCode`` 路由。
    BackendEnvelope {
        code: TaskErrorCode,
        message: String,
    },
    /// Phase 2.1 — 向运行中的任务控制器发送控制信号时,通道已关闭或
    /// 控制器不再响应。原 ``BackendExit("controller unavailable")`` 的语义。
    ControllerUnavailable,
    /// Phase 2.1 — 一次性 CLI 命令(如 ``check``)失败且无法恢复结构化
    /// 错误信封,只剩 stderr 摘要。原 ``FailedWithoutEnvelope`` 路径的语义。
    BackendProbeFailed(String),
    NdjsonDecode(serde_json::Error),
    SchemaValidation(String),
    Persistence(String),
    Io(std::io::Error),
    InvalidInput(String),
    NoActiveTask,
    /// Phase 5e — dedicated variant for failures coming back from
    /// ``open::that_detached`` (and friends). The ``open`` crate
    /// surfaces failures as plain ``std::io::Error`` values, so this
    /// variant wraps the same underlying type as ``Io`` but keeps the
    /// "OS file/folder handler failed to launch" classification
    /// separate from generic filesystem IO. Previously these were
    /// flattened into ``Io`` with a ``io::Error::new(Other, ...)``
    /// shim that lost the original error chain.
    OpenLocation(std::io::Error),
}

impl ShellError {
    pub fn code(&self) -> TaskErrorCode {
        match self {
            Self::RuntimeResolution(_) => TaskErrorCode::ProcessFailed,
            Self::Spawn(_) => TaskErrorCode::SpawnFailed,
            Self::BackendNoJson => TaskErrorCode::BackendNoJson,
            Self::BackendEnvelope { .. } => TaskErrorCode::BackendEnvelope,
            Self::ControllerUnavailable => TaskErrorCode::ControllerUnavailable,
            Self::BackendProbeFailed(_) => TaskErrorCode::BackendProbeFailed,
            Self::NdjsonDecode(_) => TaskErrorCode::SchemaMismatch,
            Self::SchemaValidation(_) => TaskErrorCode::SchemaMismatch,
            Self::Persistence(_) => TaskErrorCode::PersistenceFailed,
            Self::Io(_) => TaskErrorCode::IoError,
            Self::InvalidInput(_) => TaskErrorCode::InvalidInput,
            Self::NoActiveTask => TaskErrorCode::InvalidInput,
            Self::OpenLocation(_) => TaskErrorCode::IoError,
        }
    }
}

impl fmt::Display for ShellError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::RuntimeResolution(message) => {
                write!(f, "runtime resolution failed: {message}")
            }
            Self::Spawn(error) => write!(f, "backend spawn failed: {error}"),
            Self::BackendNoJson => {
                write!(f, "backend CLI did not emit JSON output")
            }
            Self::BackendEnvelope { code, message } => {
                write!(f, "backend error: {message} ({code:?})")
            }
            Self::ControllerUnavailable => {
                write!(f, "the running task controller is unavailable")
            }
            Self::BackendProbeFailed(message) => {
                write!(f, "backend probe failed: {message}")
            }
            Self::NdjsonDecode(error) => {
                write!(f, "backend stdout was not valid NDJSON: {error}")
            }
            Self::SchemaValidation(message) => {
                write!(f, "schema validation failed: {message}")
            }
            Self::Persistence(message) => write!(f, "persistence failed: {message}"),
            Self::Io(error) => write!(f, "io failure: {error}"),
            Self::InvalidInput(message) => write!(f, "invalid input: {message}"),
            Self::NoActiveTask => write!(f, "no running task"),
            Self::OpenLocation(error) => write!(f, "unable to open location: {error}"),
        }
    }
}

impl std::error::Error for ShellError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Spawn(error) | Self::Io(error) | Self::OpenLocation(error) => Some(error),
            Self::NdjsonDecode(error) => Some(error),
            _ => None,
        }
    }
}

impl From<std::io::Error> for ShellError {
    fn from(error: std::io::Error) -> Self {
        Self::Io(error)
    }
}

impl From<serde_json::Error> for ShellError {
    fn from(error: serde_json::Error) -> Self {
        Self::NdjsonDecode(error)
    }
}

impl Serialize for ShellError {
    fn serialize<S: Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        #[derive(Serialize)]
        #[serde(rename_all = "camelCase")]
        struct Wire<'a> {
            code: TaskErrorCode,
            message: &'a str,
        }
        let message = self.to_string();
        Wire {
            code: self.code(),
            message: &message,
        }
        .serialize(serializer)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn serializes_to_code_and_message() {
        let error = ShellError::Spawn(std::io::Error::new(
            std::io::ErrorKind::NotFound,
            "python.exe missing",
        ));
        let value = serde_json::to_value(&error).expect("serializable");
        assert_eq!(value["code"], "spawn_failed");
        assert!(value["message"]
            .as_str()
            .expect("message string")
            .contains("python.exe missing"));
    }

    #[test]
    fn invalid_input_maps_to_invalid_input_code() {
        let error = ShellError::InvalidInput("missing field foo".into());
        let value = serde_json::to_value(&error).expect("serializable");
        assert_eq!(value["code"], "invalid_input");
    }

    #[test]
    fn backend_no_json_maps_to_backend_no_json_code() {
        let error = ShellError::BackendNoJson;
        let value = serde_json::to_value(&error).expect("serializable");
        assert_eq!(value["code"], "backend_no_json");
        assert!(value["message"].as_str().unwrap().contains("did not emit JSON"));
    }

    #[test]
    fn backend_envelope_maps_to_backend_envelope_code() {
        let error = ShellError::BackendEnvelope {
            code: TaskErrorCode::MissingFfmpeg,
            message: "ffmpeg not found".into(),
        };
        let value = serde_json::to_value(&error).expect("serializable");
        assert_eq!(value["code"], "backend_envelope");
        assert!(value["message"].as_str().unwrap().contains("ffmpeg not found"));
    }

    #[test]
    fn controller_unavailable_maps_to_controller_unavailable_code() {
        let error = ShellError::ControllerUnavailable;
        let value = serde_json::to_value(&error).expect("serializable");
        assert_eq!(value["code"], "controller_unavailable");
    }

    #[test]
    fn backend_probe_failed_maps_to_backend_probe_failed_code() {
        let error = ShellError::BackendProbeFailed("dll load failed".into());
        let value = serde_json::to_value(&error).expect("serializable");
        assert_eq!(value["code"], "backend_probe_failed");
        assert!(value["message"].as_str().unwrap().contains("dll load failed"));
    }

    #[test]
    fn no_active_task_maps_to_invalid_input() {
        let value = serde_json::to_value(&ShellError::NoActiveTask).expect("serializable");
        assert_eq!(value["code"], "invalid_input");
    }

    #[test]
    fn persistence_error_routes_to_persistence_failed() {
        let error = ShellError::Persistence("disk full".into());
        let value = serde_json::to_value(&error).expect("serializable");
        assert_eq!(value["code"], "persistence_failed");
    }

    #[test]
    fn ndjson_decode_routes_to_schema_mismatch() {
        let json_error = serde_json::from_str::<serde_json::Value>("not json")
            .expect_err("invalid json must fail");
        let error: ShellError = json_error.into();
        let value = serde_json::to_value(&error).expect("serializable");
        assert_eq!(value["code"], "schema_mismatch");
    }

    #[test]
    fn open_location_routes_to_io_code_and_keeps_message() {
        let inner = std::io::Error::new(
            std::io::ErrorKind::NotFound,
            "Explorer launcher missing",
        );
        let error = ShellError::OpenLocation(inner);
        let value = serde_json::to_value(&error).expect("serializable");
        assert_eq!(value["code"], "io_error");
        assert!(value["message"]
            .as_str()
            .expect("message")
            .contains("Explorer launcher missing"));
    }

    #[test]
    fn open_location_preserves_error_source_chain() {
        // Phase 5e — the whole point of the dedicated variant is keeping
        // the inner ``io::Error`` reachable via ``Error::source``.
        let inner = std::io::Error::new(std::io::ErrorKind::PermissionDenied, "denied");
        let error = ShellError::OpenLocation(inner);
        let source = std::error::Error::source(&error).expect("source must be present");
        assert!(source.to_string().contains("denied"));
    }
}
