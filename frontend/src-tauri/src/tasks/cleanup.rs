//! Structured ownership for late lifecycle cleanup.
//!
//! The process adapter retains every stable process handle. This coordinator
//! retains the asynchronous observer that waits for both a late process reap
//! and any non-abortable process-control worker before reopening the task slot.

use std::future::Future;
use std::sync::Arc;
use std::sync::Mutex;
use std::task::Poll;

use tokio::sync::oneshot;
use tokio::task::{JoinError, JoinHandle};

use crate::process_control::ProcessControlError;
use crate::tasks::ports::TaskLifecyclePort;
use crate::tasks::state::StartLease;
use crate::tasks::subprocess::{ReapOutcome, ReapTicket};

type ControlWorkOutput = (Result<(), ProcessControlError>, bool);
type ControlWorkJoin = Result<ControlWorkOutput, JoinError>;

/// Shared structured owner for the one non-abortable process-control worker.
///
/// Polling borrows the `JoinHandle` in place, so unwinding the supervisor drops
/// only its wait future; the recovery monitor's clone still owns the handle.
#[derive(Clone, Default)]
pub(super) struct PendingControlCleanup {
    work: Arc<Mutex<Option<JoinHandle<ControlWorkOutput>>>>,
}

impl PendingControlCleanup {
    pub(super) fn start(&self, spawn: impl FnOnce() -> JoinHandle<ControlWorkOutput>) {
        let mut work = self
            .work
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        assert!(
            work.is_none(),
            "only one process-control worker may be active"
        );
        *work = Some(spawn());
    }

    pub(super) fn has_work(&self) -> bool {
        self.work
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .is_some()
    }

    pub(super) async fn wait(&self) -> Option<ControlWorkJoin> {
        std::future::poll_fn(|context| {
            let mut work = self
                .work
                .lock()
                .unwrap_or_else(std::sync::PoisonError::into_inner);
            let poll = match work.as_mut() {
                Some(handle) => std::pin::Pin::new(handle).poll(context),
                None => return Poll::Ready(None),
            };
            match poll {
                Poll::Ready(result) => {
                    work.take();
                    Poll::Ready(Some(result))
                }
                Poll::Pending => Poll::Pending,
            }
        })
        .await
    }
}

pub(super) async fn own_late_cleanup(
    lifecycle: Arc<dyn TaskLifecyclePort>,
    lease: StartLease,
    mut reap_ticket: ReapTicket,
    control_work: Option<PendingControlCleanup>,
) {
    // Do not let the observer race its own installation into TaskState. Until
    // the ready signal is sent, the CleanupFailed phase owns its JoinHandle.
    let (ready_tx, ready_rx) = oneshot::channel();
    let observer_lifecycle = Arc::clone(&lifecycle);
    let observer_lease = lease.clone();
    let observer = tokio::spawn(async move {
        if ready_rx.await.is_err() {
            return;
        }
        if let Some(control_work) = control_work {
            match control_work.wait().await {
                Some(Ok((Ok(()), _))) => {}
                Some(Ok((Err(error), _))) => {
                    eprintln!("late process-control cleanup completed with an error: {error}");
                }
                Some(Err(error)) => {
                    eprintln!("late process-control cleanup worker failed: {error}");
                }
                None => eprintln!("late process-control cleanup lost its worker ownership"),
            }
        }
        match reap_ticket.wait().await {
            ReapOutcome::Reaped => {
                if !observer_lifecycle.confirm_cleanup(&observer_lease).await {
                    eprintln!("late process cleanup no longer owns its task lease");
                }
            }
            ReapOutcome::Failed(error) => {
                eprintln!("late process cleanup could not confirm reap: {error}");
            }
        }
    });

    if lifecycle.own_cleanup_observer(&lease, observer).await {
        if ready_tx.send(()).is_err() {
            eprintln!("late process cleanup observer stopped before it was activated");
        }
    } else {
        eprintln!("late process cleanup observer could not acquire its task lease");
    }
}
