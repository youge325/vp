//! Consumer-owned ports for the task application service.

use std::future::Future;
use std::pin::Pin;

use tokio::task::JoinHandle;

use crate::models::{
    ResumeStatusPayload, TaskCancelledPayload, TaskCompletedPayload, TaskErrorPayload,
    TaskLogPayload, TaskProgressPayload,
};
use crate::tasks::cancellation::CancelReason;
use crate::tasks::state::StartLease;

pub(super) enum TaskDomainEvent {
    Progress(TaskProgressPayload),
    ResumeStatus(ResumeStatusPayload),
    Log(TaskLogPayload),
    Completed(TaskCompletedPayload),
    Error(TaskErrorPayload),
    Cancelled(TaskCancelledPayload),
}

pub(super) trait TaskEventSink: Send + Sync {
    fn emit(&self, event: TaskDomainEvent) -> Result<(), String>;
}

pub(super) type LifecycleFuture<'a> = Pin<Box<dyn Future<Output = bool> + Send + 'a>>;

pub(super) trait TaskLifecyclePort: Send + Sync {
    fn begin_reaping<'a>(&'a self, lease: &'a StartLease) -> LifecycleFuture<'a>;
    fn cancel_owned<'a>(
        &'a self,
        lease: &'a StartLease,
        reason: CancelReason,
    ) -> LifecycleFuture<'a>;
    fn seal_owned<'a>(&'a self, lease: &'a StartLease) -> LifecycleFuture<'a>;
    fn finish_once<'a>(
        &'a self,
        lease: &'a StartLease,
        before_release: Box<dyn FnOnce() + Send + 'static>,
    ) -> LifecycleFuture<'a>;
    fn fail_cleanup_once<'a>(
        &'a self,
        lease: &'a StartLease,
        terminal: Box<dyn FnOnce() + Send + 'static>,
    ) -> LifecycleFuture<'a>;
    fn own_cleanup_observer<'a>(
        &'a self,
        lease: &'a StartLease,
        observer: JoinHandle<()>,
    ) -> LifecycleFuture<'a>;
    fn confirm_cleanup<'a>(&'a self, lease: &'a StartLease) -> LifecycleFuture<'a>;
}
