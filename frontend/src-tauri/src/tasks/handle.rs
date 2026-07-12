//! Public handle returned by ``spawn_task`` and stored in ``TaskState``.
//!
//! Encapsulates the two channels the running task is steered by:
//! - ``control_tx`` for blocking pause/resume requests (responses are
//!   returned over a oneshot the controller fills synchronously),
//! - ``cancel_token`` for fire-and-forget cancellation (no dropped
//!   signal under load, unlike the previous bounded mpsc).
//!
//! The struct is cheap to ``Clone`` (everything inside is ``Arc``-wrapped),
//! so it can be stored in the global ``TaskState`` mutex and cloned out
//! whenever a command needs to dispatch a control signal.

use tokio::sync::mpsc;

use crate::tasks::cancellation::{CancelReason, CancellationToken};
use crate::tasks::TaskControlMessage;

#[derive(Clone)]
pub(crate) struct TaskHandle {
    pub(crate) control_tx: mpsc::Sender<TaskControlMessage>,
    pub(crate) cancel_token: CancellationToken,
}

impl TaskHandle {
    pub(crate) fn new(
        control_tx: mpsc::Sender<TaskControlMessage>,
        cancel_token: CancellationToken,
    ) -> Self {
        Self {
            control_tx,
            cancel_token,
        }
    }

    /// Idempotent: subsequent calls are no-ops at the token level.
    pub(crate) fn cancel(&self, reason: CancelReason) {
        self.cancel_token.cancel(reason);
    }
}
