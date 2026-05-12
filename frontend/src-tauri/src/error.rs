//! Structured shell-side error type for Tauri commands.
//!
//! Replaces the legacy `Result<T, String>` convention with a typed enum that
//! maps to `protocol::TaskErrorCode`. The custom `Serialize` impl emits
//! `{ code, message }` so the frontend can route on `code` rather than parse
//! free-form strings.

use std::fmt;

use serde::{Serialize, Serializer};

use crate::protocol::TaskErrorCode;

#[derive(Debug)]
pub enum ShellError {
    RuntimeResolution(String),
    Spawn(std::io::Error),
    BackendExit(String),
    NdjsonDecode(serde_json::Error),
    SchemaValidation(String),
    Persistence(String),
    Io(std::io::Error),
    InvalidInput(String),
    NoActiveTask,
    Other(String),
}

impl ShellError {
    pub fn code(&self) -> TaskErrorCode {
        match self {
            Self::RuntimeResolution(_) => TaskErrorCode::ProcessFailed,
            Self::Spawn(_) => TaskErrorCode::SpawnFailed,
            Self::BackendExit(_) => TaskErrorCode::RuntimePanic,
            Self::NdjsonDecode(_) => TaskErrorCode::SchemaMismatch,
            Self::SchemaValidation(_) => TaskErrorCode::SchemaMismatch,
            Self::Persistence(_) => TaskErrorCode::PersistenceFailed,
            Self::Io(_) => TaskErrorCode::IoError,
            Self::InvalidInput(_) => TaskErrorCode::InvalidInput,
            Self::NoActiveTask => TaskErrorCode::InvalidInput,
            Self::Other(_) => TaskErrorCode::ProcessFailed,
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
            Self::BackendExit(message) => {
                write!(f, "backend exited unexpectedly: {message}")
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
            Self::Other(message) => f.write_str(message),
        }
    }
}

impl std::error::Error for ShellError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Spawn(error) | Self::Io(error) => Some(error),
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

impl From<String> for ShellError {
    fn from(message: String) -> Self {
        Self::Other(message)
    }
}

impl From<&str> for ShellError {
    fn from(message: &str) -> Self {
        Self::Other(message.to_string())
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
    fn other_falls_back_to_process_failed() {
        let error: ShellError = String::from("legacy untyped string").into();
        let value = serde_json::to_value(&error).expect("serializable");
        assert_eq!(value["code"], "process_failed");
        assert_eq!(value["message"], "legacy untyped string");
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
}
