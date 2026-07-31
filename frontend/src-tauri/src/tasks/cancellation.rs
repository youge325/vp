//! Cancellation token whose state and reason are one atomic value.

use std::sync::atomic::{AtomicU8, Ordering};
use std::sync::Arc;

use tokio::sync::Notify;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(super) enum CancelReason {
    User,
    Stalled,
}

impl CancelReason {
    const fn as_u8(self) -> u8 {
        match self {
            Self::User => 1,
            Self::Stalled => 2,
        }
    }

    const fn from_u8(value: u8) -> Option<Self> {
        match value {
            1 => Some(Self::User),
            2 => Some(Self::Stalled),
            _ => None,
        }
    }
}

#[derive(Debug, Default)]
struct CancellationInner {
    state: AtomicU8,
    notify: Notify,
}

#[derive(Debug, Clone, Default)]
pub(super) struct CancellationToken {
    inner: Arc<CancellationInner>,
}

impl CancellationToken {
    pub(super) fn new() -> Self {
        Self::default()
    }

    /// Atomically install the first cancellation reason and wake all waiters.
    pub(super) fn cancel(&self, reason: CancelReason) -> bool {
        if self
            .inner
            .state
            .compare_exchange(0, reason.as_u8(), Ordering::AcqRel, Ordering::Acquire)
            .is_ok()
        {
            self.inner.notify.notify_waiters();
            true
        } else {
            false
        }
    }

    pub(super) fn is_cancelled(&self) -> bool {
        self.inner.state.load(Ordering::Acquire) != 0
    }

    pub(super) fn reason(&self) -> Option<CancelReason> {
        CancelReason::from_u8(self.inner.state.load(Ordering::Acquire))
    }

    pub(super) async fn cancelled(&self) {
        loop {
            let notified = self.inner.notify.notified();
            tokio::pin!(notified);
            notified.as_mut().enable();
            if self.is_cancelled() {
                return;
            }
            notified.await;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Barrier;
    use std::time::Duration;

    #[test]
    fn fresh_token_has_no_cancellation_reason() {
        let token = CancellationToken::new();

        assert!(!token.is_cancelled());
        assert_eq!(token.reason(), None);
    }

    #[tokio::test]
    async fn cancel_atomically_sets_reason_and_wakes_waiters() {
        let token = CancellationToken::new();
        let waiter = {
            let token = token.clone();
            tokio::spawn(async move { token.cancelled().await })
        };

        tokio::task::yield_now().await;
        assert!(token.cancel(CancelReason::User));
        waiter.await.expect("waiter");
        assert_eq!(token.reason(), Some(CancelReason::User));
    }

    #[test]
    fn first_reason_wins_without_torn_cancelled_state() {
        let token = CancellationToken::new();
        assert!(token.cancel(CancelReason::Stalled));
        assert!(!token.cancel(CancelReason::User));
        assert!(token.is_cancelled());
        assert_eq!(token.reason(), Some(CancelReason::Stalled));
    }

    #[tokio::test]
    async fn cancelled_resolves_immediately_when_already_cancelled() {
        let token = CancellationToken::new();
        token.cancel(CancelReason::User);
        tokio::time::timeout(Duration::from_millis(50), token.cancelled())
            .await
            .expect("must resolve immediately");
    }

    #[tokio::test]
    async fn one_cancellation_wakes_every_registered_waiter() {
        let token = CancellationToken::new();
        let first = {
            let token = token.clone();
            tokio::spawn(async move { token.cancelled().await })
        };
        let second = {
            let token = token.clone();
            tokio::spawn(async move { token.cancelled().await })
        };

        tokio::task::yield_now().await;
        assert!(token.cancel(CancelReason::Stalled));
        tokio::time::timeout(Duration::from_millis(100), async {
            first.await.expect("first waiter");
            second.await.expect("second waiter");
        })
        .await
        .expect("all waiters must wake");
    }

    #[test]
    fn clones_observe_the_same_first_reason() {
        let token = CancellationToken::new();
        let clone = token.clone();

        assert!(clone.cancel(CancelReason::User));
        assert!(token.is_cancelled());
        assert_eq!(token.reason(), Some(CancelReason::User));
    }

    #[test]
    fn competing_reasons_have_exactly_one_cas_winner() {
        let token = CancellationToken::new();
        let barrier = Arc::new(Barrier::new(3));
        let user = {
            let token = token.clone();
            let barrier = Arc::clone(&barrier);
            std::thread::spawn(move || {
                barrier.wait();
                token.cancel(CancelReason::User)
            })
        };
        let stalled = {
            let token = token.clone();
            let barrier = Arc::clone(&barrier);
            std::thread::spawn(move || {
                barrier.wait();
                token.cancel(CancelReason::Stalled)
            })
        };

        barrier.wait();
        let user_won = user.join().expect("user contender");
        let stalled_won = stalled.join().expect("stalled contender");
        assert_ne!(user_won, stalled_won, "exactly one CAS must succeed");
        assert_eq!(
            token.reason(),
            Some(if user_won {
                CancelReason::User
            } else {
                CancelReason::Stalled
            })
        );
    }
}
