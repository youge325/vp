//! Structured shell-side error type for Tauri commands.
//!
//! The typed enum maps to the generated shell/backend code subsets. Its custom `Serialize`
//! impl emits `{ code, message, details? }` so the frontend can route on
//! `code` and retain backend context instead of parsing free-form strings.
//!
//! Catch-all string conversions are intentionally absent. Any new failure
//! must pick a named variant: runtime discovery uses `RuntimeResolution`,
//! one-shot backend failures use `BackendProbeFailed`, process supervision
//! uses `ProcessFailed`, and storage IO uses `Persistence`. This keeps the
//! wire-level `code` field meaningful for the frontend.

use std::fmt;

use serde::{Serialize, Serializer};

use crate::models::{BackendTaskErrorCode, BackendTaskErrorPayload, ShellTaskErrorCode};
use crate::process_control::ProcessControlError;

#[derive(Clone, Copy, Serialize)]
#[serde(untagged)]
enum WireErrorCode {
    Backend(BackendTaskErrorCode),
    Shell(ShellTaskErrorCode),
}

#[derive(Debug)]
pub(crate) enum ShellError {
    RuntimeResolution(String),
    Spawn(std::io::Error),
    /// CLI 成功退出但未在 stdout 上输出有效 JSON。
    BackendNoJson,
    /// 后端返回的结构化错误信封，完整保留 code/message/details。
    BackendEnvelope(BackendTaskErrorPayload),
    /// 向运行中的任务控制器发送控制信号时，通道已关闭或控制器不再响应。
    ControllerUnavailable,
    /// 一次性 CLI 命令失败且无法恢复结构化错误信封，只剩 stderr 摘要。
    BackendProbeFailed(String),
    /// pause / resume 控制信号已送达控制器,但控制器调
    /// ``ProcessController::suspend/resume`` 失败,例如目标 PID 已退出、
    /// OS 拒绝权限。和 ``ControllerUnavailable``(通道断/超时)分开,
    /// 让前端可以区分"任务已结束"与"控制层崩了"。
    ProcessControl(ProcessControlError),
    SchemaValidation(String),
    Persistence(String),
    Io(std::io::Error),
    InvalidInput(String),
    NoActiveTask,
    /// Dedicated variant for failures coming back from
    /// ``open::that_detached``. The ``open`` crate
    /// surfaces failures as plain ``std::io::Error`` values, so this
    /// variant wraps the same underlying type as ``Io`` but keeps the
    /// "OS file/folder handler failed to launch" classification
    /// separate from generic filesystem IO without losing the source chain.
    OpenLocation(std::io::Error),
}

impl ShellError {
    fn code(&self) -> WireErrorCode {
        match self {
            Self::RuntimeResolution(_) => WireErrorCode::Shell(ShellTaskErrorCode::ProcessFailed),
            Self::Spawn(_) => WireErrorCode::Shell(ShellTaskErrorCode::SpawnFailed),
            Self::BackendNoJson => WireErrorCode::Shell(ShellTaskErrorCode::BackendNoJson),
            Self::BackendEnvelope(payload) => WireErrorCode::Backend(payload.code),
            Self::ControllerUnavailable => {
                WireErrorCode::Shell(ShellTaskErrorCode::ControllerUnavailable)
            }
            Self::BackendProbeFailed(_) => {
                WireErrorCode::Shell(ShellTaskErrorCode::BackendProbeFailed)
            }
            Self::ProcessControl(_) => WireErrorCode::Shell(ShellTaskErrorCode::ProcessFailed),
            Self::SchemaValidation(_) => WireErrorCode::Shell(ShellTaskErrorCode::SchemaMismatch),
            Self::Persistence(_) => WireErrorCode::Shell(ShellTaskErrorCode::PersistenceFailed),
            Self::Io(_) => WireErrorCode::Shell(ShellTaskErrorCode::IoError),
            Self::InvalidInput(_) => WireErrorCode::Shell(ShellTaskErrorCode::InvalidInput),
            Self::NoActiveTask => WireErrorCode::Shell(ShellTaskErrorCode::InvalidInput),
            Self::OpenLocation(_) => WireErrorCode::Shell(ShellTaskErrorCode::IoError),
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
            Self::BackendEnvelope(payload) => {
                write!(f, "backend error: {} ({:?})", payload.message, payload.code)
            }
            Self::ControllerUnavailable => {
                write!(f, "the running task controller is unavailable")
            }
            Self::BackendProbeFailed(message) => {
                write!(f, "backend probe failed: {message}")
            }
            Self::ProcessControl(error) => write!(f, "process control failed: {error}"),
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
            Self::ProcessControl(error) => Some(error),
            _ => None,
        }
    }
}

impl From<std::io::Error> for ShellError {
    fn from(error: std::io::Error) -> Self {
        Self::Io(error)
    }
}

impl Serialize for ShellError {
    fn serialize<S: Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        #[derive(Serialize)]
        #[serde(rename_all = "camelCase")]
        struct Wire<'a> {
            code: WireErrorCode,
            message: &'a str,
            #[serde(skip_serializing_if = "Option::is_none")]
            details: Option<&'a serde_json::Map<String, serde_json::Value>>,
        }
        let message = self.to_string();
        let (wire_message, details) = match self {
            Self::BackendEnvelope(payload) => (payload.message.as_str(), payload.details.as_ref()),
            _ => (message.as_str(), None),
        };
        Wire {
            code: self.code(),
            message: wire_message,
            details,
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
        assert!(value["message"]
            .as_str()
            .unwrap()
            .contains("did not emit JSON"));
    }

    #[test]
    fn backend_envelope_preserves_wire_fields_exactly() {
        let error = ShellError::BackendEnvelope(BackendTaskErrorPayload {
            code: BackendTaskErrorCode::MissingFfmpeg,
            message: "ffmpeg not found".into(),
            details: Some(serde_json::Map::from_iter([(
                "path".to_string(),
                serde_json::Value::String("ffmpeg".to_string()),
            )])),
        });
        let value = serde_json::to_value(&error).expect("serializable");
        assert_eq!(value["code"], "missing_ffmpeg");
        assert_eq!(value["message"], "ffmpeg not found");
        assert_eq!(value["details"]["path"], "ffmpeg");
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
        assert!(value["message"]
            .as_str()
            .unwrap()
            .contains("dll load failed"));
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
    fn open_location_routes_to_io_code_and_keeps_message() {
        let inner = std::io::Error::new(std::io::ErrorKind::NotFound, "Explorer launcher missing");
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
        let inner = std::io::Error::new(std::io::ErrorKind::PermissionDenied, "denied");
        let error = ShellError::OpenLocation(inner);
        let source = std::error::Error::source(&error).expect("source must be present");
        assert!(source.to_string().contains("denied"));
    }

    #[test]
    fn runtime_resolution_uses_process_failed_without_details() {
        let value = serde_json::to_value(ShellError::RuntimeResolution(
            "runtime root is missing".to_string(),
        ))
        .expect("serializable");

        assert_eq!(value["code"], "process_failed");
        assert!(value["message"]
            .as_str()
            .expect("message")
            .starts_with("runtime resolution failed:"));
        assert!(value.get("details").is_none());
    }

    #[test]
    fn schema_validation_uses_schema_mismatch_code() {
        let value = serde_json::to_value(ShellError::SchemaValidation("unknown field".to_string()))
            .expect("serializable");

        assert_eq!(value["code"], "schema_mismatch");
        assert!(value["message"]
            .as_str()
            .expect("message")
            .contains("unknown field"));
    }

    #[test]
    fn generic_io_error_keeps_its_source_and_wire_code() {
        let error = ShellError::Io(std::io::Error::new(
            std::io::ErrorKind::PermissionDenied,
            "read denied",
        ));
        assert!(std::error::Error::source(&error)
            .expect("io source")
            .to_string()
            .contains("read denied"));

        let value = serde_json::to_value(error).expect("serializable");
        assert_eq!(value["code"], "io_error");
    }

    #[test]
    fn spawn_error_keeps_its_source_chain() {
        let error = ShellError::Spawn(std::io::Error::new(
            std::io::ErrorKind::NotFound,
            "backend executable missing",
        ));

        assert!(std::error::Error::source(&error)
            .expect("spawn source")
            .to_string()
            .contains("backend executable missing"));
    }

    #[test]
    fn process_control_error_keeps_source_and_process_failed_code() {
        let error = ShellError::ProcessControl(ProcessControlError::Os(std::io::Error::new(
            std::io::ErrorKind::PermissionDenied,
            "suspend denied",
        )));
        assert!(std::error::Error::source(&error).is_some());

        let value = serde_json::to_value(error).expect("serializable");
        assert_eq!(value["code"], "process_failed");
        assert!(value["message"]
            .as_str()
            .expect("message")
            .contains("suspend denied"));
    }

    #[test]
    fn backend_envelope_without_details_omits_the_wire_property() {
        let error = ShellError::BackendEnvelope(BackendTaskErrorPayload {
            code: BackendTaskErrorCode::MissingModel,
            message: "model unavailable".to_string(),
            details: None,
        });
        let value = serde_json::to_value(error).expect("serializable");

        assert_eq!(value["code"], "missing_model");
        assert_eq!(value["message"], "model unavailable");
        assert!(value.get("details").is_none());
    }

    #[test]
    fn from_io_error_uses_the_generic_io_variant() {
        let error: ShellError = std::io::Error::other("filesystem unavailable").into();

        assert!(matches!(error, ShellError::Io(_)));
    }
}
