use std::collections::VecDeque;
use std::sync::{Arc, Mutex};

const STDERR_CAPTURE_LINE_LIMIT: usize = 400;
const STDERR_CAPTURE_BYTE_LIMIT: usize = 8 * 1024;

const TRACEBACK_MARKER: &str = "Traceback (most recent call last):";

#[derive(Debug, Default, Clone)]
pub struct StderrCapture {
    inner: Arc<Mutex<StderrCaptureInner>>,
}

#[derive(Debug, Default)]
struct StderrCaptureInner {
    recent_lines: VecDeque<String>,
}

impl StderrCapture {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn record(&self, line: &str) {
        if line.is_empty() {
            return;
        }
        if let Ok(mut inner) = self.inner.lock() {
            inner.recent_lines.push_back(line.to_string());
            while inner.recent_lines.len() > STDERR_CAPTURE_LINE_LIMIT {
                inner.recent_lines.pop_front();
            }
        }
    }

    /// Returns a compact summary that prefers the most recent Python
    /// traceback. Falls back to the trailing slice of stderr lines if no
    /// traceback marker is present.
    pub fn summary(&self) -> Option<String> {
        let lines = self.inner.lock().ok()?.recent_lines.clone();
        if lines.is_empty() {
            return None;
        }
        let start = lines
            .iter()
            .rposition(|line| line.contains(TRACEBACK_MARKER))
            .unwrap_or_else(|| lines.len().saturating_sub(20));
        let slice = lines.iter().skip(start).cloned().collect::<Vec<_>>();
        Some(truncate(slice.join("\n"), STDERR_CAPTURE_BYTE_LIMIT))
    }
}

fn truncate(mut text: String, max_bytes: usize) -> String {
    if text.len() <= max_bytes {
        return text;
    }
    // Drop from the front; we want the tail (recent context).
    let cut = text.len() - max_bytes;
    let valid_cut = text
        .char_indices()
        .find(|(idx, _)| *idx >= cut)
        .map(|(idx, _)| idx)
        .unwrap_or(text.len());
    text.replace_range(..valid_cut, "[...truncated]\n");
    text
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn summary_returns_none_when_empty() {
        let capture = StderrCapture::new();
        assert!(capture.summary().is_none());
    }

    #[test]
    fn summary_returns_tail_when_no_traceback_present() {
        let capture = StderrCapture::new();
        for index in 0..50 {
            capture.record(&format!("line {index}"));
        }
        let summary = capture.summary().expect("summary");
        assert!(summary.starts_with("line 30"));
        assert!(summary.ends_with("line 49"));
    }

    #[test]
    fn summary_starts_from_last_traceback_marker() {
        let capture = StderrCapture::new();
        capture.record("[VP_PROGRESS] 1/10");
        capture.record("Traceback (most recent call last):");
        capture.record("  File \"app.py\", line 12, in <module>");
        capture.record("ImportError: No module named torch");
        let summary = capture.summary().expect("summary");
        assert!(summary.starts_with("Traceback"));
        assert!(summary.contains("No module named torch"));
        assert!(!summary.contains("VP_PROGRESS"));
    }

    #[test]
    fn summary_prefers_latest_traceback() {
        let capture = StderrCapture::new();
        capture.record("Traceback (most recent call last):");
        capture.record("RuntimeError: first failure");
        capture.record("[handler retried]");
        capture.record("Traceback (most recent call last):");
        capture.record("RuntimeError: second failure");
        let summary = capture.summary().expect("summary");
        assert!(summary.contains("second failure"));
        assert!(!summary.contains("first failure"));
    }

    #[test]
    fn summary_is_truncated_when_oversized() {
        let capture = StderrCapture::new();
        let chunk = "a".repeat(2048);
        for _ in 0..10 {
            capture.record(&chunk);
        }
        let summary = capture.summary().expect("summary");
        assert!(summary.len() <= STDERR_CAPTURE_BYTE_LIMIT + "[...truncated]\n".len());
    }
}
