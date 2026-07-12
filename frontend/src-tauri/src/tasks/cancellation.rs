//! Lightweight cancellation primitive shared by the task runner.
//!
//! Hand-rolled (vs. pulling in `tokio_util::sync::CancellationToken`) to avoid
//! the extra dependency for a single feature. Semantically equivalent for
//! our needs: idempotent ``cancel()``, multi-reader ``cancelled()`` future,
//! cheap ``Clone`` (shares an ``Arc``).

use std::sync::atomic::{AtomicBool, AtomicU8, Ordering};
use std::sync::Arc;

use tokio::sync::Notify;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum CancelReason {
    User,
    Stalled,
}

impl CancelReason {
    fn as_u8(self) -> u8 {
        match self {
            Self::User => 1,
            Self::Stalled => 2,
        }
    }

    fn from_u8(value: u8) -> Option<Self> {
        match value {
            1 => Some(Self::User),
            2 => Some(Self::Stalled),
            _ => None,
        }
    }
}

#[derive(Debug, Default)]
struct CancellationInner {
    cancelled: AtomicBool,
    reason: AtomicU8,
    notify: Notify,
}

#[derive(Debug, Clone, Default)]
pub(crate) struct CancellationToken {
    inner: Arc<CancellationInner>,
}

impl CancellationToken {
    pub(crate) fn new() -> Self {
        Self::default()
    }

    /// Mark the token as cancelled. First call wins for the reason and
    /// wakes all current ``cancelled()`` waiters. Subsequent calls are
    /// no-ops (no dropped signal — unlike a bounded mpsc).
    pub(crate) fn cancel(&self, reason: CancelReason) {
        if !self.inner.cancelled.swap(true, Ordering::SeqCst) {
            self.inner.reason.store(reason.as_u8(), Ordering::SeqCst);
            self.inner.notify.notify_waiters();
        }
    }

    pub(crate) fn is_cancelled(&self) -> bool {
        self.inner.cancelled.load(Ordering::SeqCst)
    }

    pub(crate) fn reason(&self) -> Option<CancelReason> {
        CancelReason::from_u8(self.inner.reason.load(Ordering::SeqCst))
    }

    /// Resolves once the token is cancelled. Safe to call from multiple
    /// tasks concurrently.
    pub(crate) async fn cancelled(&self) {
        if self.is_cancelled() {
            return;
        }
        loop {
            // Build the future, then ``enable()`` it (registers the waker
            // before we yield). Without this, ``notify_waiters()`` could fire
            // in the race window between the atomic check above and the
            // first poll of ``notified``, dropping the wake-up.
            let notified = self.inner.notify.notified();
            tokio::pin!(notified);
            notified.as_mut().enable();
            if self.is_cancelled() {
                return;
            }
            notified.await;
            if self.is_cancelled() {
                return;
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Duration;

    #[tokio::test]
    async fn cancel_sets_reason_and_wakes_waiters() {
        let token = CancellationToken::new();
        let task = {
            let token = token.clone();
            tokio::spawn(async move {
                token.cancelled().await;
            })
        };

        // Give the spawned task a chance to park on `cancelled()`.
        tokio::time::sleep(Duration::from_millis(10)).await;
        assert!(!token.is_cancelled());

        token.cancel(CancelReason::User);
        task.await.unwrap();
        assert!(token.is_cancelled());
        assert_eq!(token.reason(), Some(CancelReason::User));
    }

    #[tokio::test]
    async fn second_cancel_does_not_overwrite_reason() {
        let token = CancellationToken::new();
        token.cancel(CancelReason::Stalled);
        token.cancel(CancelReason::User); // ignored
        assert_eq!(token.reason(), Some(CancelReason::Stalled));
    }

    #[tokio::test]
    async fn cancelled_resolves_immediately_when_already_cancelled() {
        let token = CancellationToken::new();
        token.cancel(CancelReason::User);
        // Should not hang.
        tokio::time::timeout(Duration::from_millis(50), token.cancelled())
            .await
            .expect("must resolve immediately");
    }
}
