//! Backend pipe readers.
//!
//! Readers only parse and forward observations. The task supervisor owns all
//! event emission and terminal-state decisions.

use std::sync::{Arc, Mutex};
use std::time::Instant;

use tokio::io::{AsyncWrite, AsyncWriteExt, BufReader};
use tokio::sync::mpsc;
use tokio::task::JoinHandle;
use tokio::time::Duration;

use crate::generated::{BackendProcessSpec, StartTaskSpec, NDJSON_LINE_LIMIT_BYTES};
use crate::models::TaskErrorCode;
use crate::tasks::bounded_io::read_ndjson_line;
use crate::tasks::envelope::{classify_line, ClassifiedLine};
use crate::tasks::stderr::StderrCapture;

pub(super) type ProgressBeat = Arc<Mutex<Instant>>;

#[derive(Debug)]
pub(super) enum ReaderMessage {
    Stdout(ClassifiedLine),
    Stderr(String),
    PipeFailure {
        stream: &'static str,
        operation: &'static str,
        message: String,
    },
}

pub(super) fn spawn_stdout_reader(
    stdout: tokio::process::ChildStdout,
    tx: mpsc::Sender<ReaderMessage>,
    progress_beat: ProgressBeat,
) -> JoinHandle<()> {
    tokio::spawn(async move {
        let mut reader = BufReader::new(stdout);
        loop {
            match read_ndjson_line(&mut reader, NDJSON_LINE_LIMIT_BYTES).await {
                Ok(Some(line)) => {
                    let classified = classify_line(&line);
                    if matches!(classified, ClassifiedLine::Progress(_)) {
                        if let Ok(mut guard) = progress_beat.lock() {
                            *guard = Instant::now();
                        }
                    }
                    if tx.send(ReaderMessage::Stdout(classified)).await.is_err() {
                        break;
                    }
                }
                Ok(None) => break,
                Err(error) => {
                    let _ = tx
                        .send(ReaderMessage::PipeFailure {
                            stream: "stdout",
                            operation: "read",
                            message: error.to_string(),
                        })
                        .await;
                    break;
                }
            }
        }
    })
}

pub(super) fn spawn_stderr_reader(
    stderr: tokio::process::ChildStderr,
    tx: mpsc::Sender<ReaderMessage>,
    capture: StderrCapture,
) -> JoinHandle<()> {
    tokio::spawn(async move {
        let mut reader = BufReader::new(stderr);
        loop {
            match read_ndjson_line(&mut reader, NDJSON_LINE_LIMIT_BYTES).await {
                Ok(Some(line)) => {
                    let trimmed = line.trim();
                    if trimmed.is_empty() {
                        continue;
                    }
                    capture.record(trimmed);
                    if tx
                        .send(ReaderMessage::Stderr(trimmed.to_string()))
                        .await
                        .is_err()
                    {
                        break;
                    }
                }
                Ok(None) => break,
                Err(error) => {
                    let _ = tx
                        .send(ReaderMessage::PipeFailure {
                            stream: "stderr",
                            operation: "read",
                            message: error.to_string(),
                        })
                        .await;
                    break;
                }
            }
        }
    })
}

pub(super) fn spawn_stdin_writer(
    stdin: tokio::process::ChildStdin,
    payload: String,
    tx: mpsc::Sender<ReaderMessage>,
) -> JoinHandle<()> {
    tokio::spawn(async move {
        if let Err(message) =
            write_payload_with_timeout(stdin, payload.as_bytes(), StartTaskSpec::STDIN_TIMEOUT)
                .await
        {
            let _ = tx
                .send(ReaderMessage::PipeFailure {
                    stream: "stdin",
                    operation: "write",
                    message,
                })
                .await;
        }
    })
}

async fn write_payload_with_timeout<W: AsyncWrite + Unpin>(
    mut writer: W,
    payload: &[u8],
    duration: Duration,
) -> Result<(), String> {
    tokio::time::timeout(duration, async {
        writer.write_all(payload).await?;
        writer.flush().await?;
        Ok::<(), std::io::Error>(())
    })
    .await
    .map_err(|_| format!("timed out after {} seconds", duration.as_secs_f64()))?
    .map_err(|error| error.to_string())
}

pub(super) fn pipe_failure_payload(
    stream: &str,
    operation: &str,
    message: String,
) -> crate::models::TaskErrorPayload {
    crate::models::TaskErrorPayload {
        code: TaskErrorCode::ProcessFailed,
        message: format!("Failed to {operation} backend {stream}: {message}"),
        details: None,
    }
}

#[cfg(test)]
mod tests {
    use super::{pipe_failure_payload, write_payload_with_timeout};
    use crate::models::TaskErrorCode;
    use tokio::io::{duplex, AsyncReadExt};
    use tokio::time::Duration;

    #[tokio::test]
    async fn stdin_payload_write_is_bounded_when_the_backend_does_not_read() {
        let (writer, _reader) = duplex(1);
        let result =
            write_payload_with_timeout(writer, b"payload", Duration::from_millis(20)).await;
        assert!(result.expect_err("must time out").contains("timed out"));
    }

    #[tokio::test]
    async fn stdin_payload_is_fully_written_when_the_backend_reads() {
        let (writer, mut reader) = duplex(32);
        let reader_task = tokio::spawn(async move {
            let mut bytes = Vec::new();
            reader.read_to_end(&mut bytes).await.expect("read");
            bytes
        });
        write_payload_with_timeout(writer, b"payload", Duration::from_millis(100))
            .await
            .expect("write");
        assert_eq!(reader_task.await.expect("reader"), b"payload");
    }

    #[tokio::test]
    async fn stdin_writer_surfaces_a_closed_backend_pipe() {
        let (writer, reader) = duplex(8);
        drop(reader);

        let error = write_payload_with_timeout(writer, b"payload", Duration::from_millis(100))
            .await
            .expect_err("closed pipe");
        assert!(!error.contains("timed out"));
        assert!(!error.is_empty());
    }

    #[test]
    fn pipe_failure_payload_identifies_stream_and_operation() {
        let payload = pipe_failure_payload("stderr", "read", "broken pipe".to_string());

        assert!(matches!(payload.code, TaskErrorCode::ProcessFailed));
        assert_eq!(
            payload.message,
            "Failed to read backend stderr: broken pipe"
        );
        assert!(payload.details.is_none());
    }
}
