//! Consumer-owned ports between the task application service and Tauri.

use std::future::Future;
use std::pin::Pin;

use tauri::{AppHandle, Emitter, Manager, Runtime};
use tokio::task::JoinHandle;

use crate::generated::TaskEventName;
use crate::models::{
    ResumeStatusPayload, TaskCancelledPayload, TaskCompletedPayload, TaskErrorPayload,
    TaskLogPayload, TaskProgressPayload,
};
use crate::tasks::cancellation::CancelReason;
use crate::tasks::state::StartLease;
use crate::tasks::TaskState;

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

type LifecycleFuture<'a> = Pin<Box<dyn Future<Output = bool> + Send + 'a>>;

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

pub(super) struct TauriTaskPorts<R: Runtime> {
    app: AppHandle<R>,
}

impl<R: Runtime> TauriTaskPorts<R> {
    pub(super) fn new(app: AppHandle<R>) -> Self {
        Self { app }
    }
}

impl<R: Runtime> TaskEventSink for TauriTaskPorts<R> {
    fn emit(&self, event: TaskDomainEvent) -> Result<(), String> {
        let result = match event {
            TaskDomainEvent::Progress(payload) => {
                self.app.emit(TaskEventName::TaskProgress.as_str(), payload)
            }
            TaskDomainEvent::ResumeStatus(payload) => self
                .app
                .emit(TaskEventName::TaskResumeStatus.as_str(), payload),
            TaskDomainEvent::Log(payload) => {
                self.app.emit(TaskEventName::TaskLog.as_str(), payload)
            }
            TaskDomainEvent::Completed(payload) => self
                .app
                .emit(TaskEventName::TaskCompleted.as_str(), payload),
            TaskDomainEvent::Error(payload) => {
                self.app.emit(TaskEventName::TaskError.as_str(), payload)
            }
            TaskDomainEvent::Cancelled(payload) => self
                .app
                .emit(TaskEventName::TaskCancelled.as_str(), payload),
        };
        result.map_err(|error| error.to_string())
    }
}

impl<R: Runtime> TaskLifecyclePort for TauriTaskPorts<R> {
    fn begin_reaping<'a>(&'a self, lease: &'a StartLease) -> LifecycleFuture<'a> {
        Box::pin(async move { self.app.state::<TaskState>().begin_reaping(lease).await })
    }

    fn cancel_owned<'a>(
        &'a self,
        lease: &'a StartLease,
        reason: CancelReason,
    ) -> LifecycleFuture<'a> {
        Box::pin(async move {
            self.app
                .state::<TaskState>()
                .cancel_owned(lease, reason)
                .await
        })
    }

    fn seal_owned<'a>(&'a self, lease: &'a StartLease) -> LifecycleFuture<'a> {
        Box::pin(async move { self.app.state::<TaskState>().seal_owned(lease).await })
    }

    fn finish_once<'a>(
        &'a self,
        lease: &'a StartLease,
        before_release: Box<dyn FnOnce() + Send + 'static>,
    ) -> LifecycleFuture<'a> {
        Box::pin(async move {
            self.app
                .state::<TaskState>()
                .finish_once(lease, before_release)
                .await
        })
    }

    fn fail_cleanup_once<'a>(
        &'a self,
        lease: &'a StartLease,
        terminal: Box<dyn FnOnce() + Send + 'static>,
    ) -> LifecycleFuture<'a> {
        Box::pin(async move {
            self.app
                .state::<TaskState>()
                .fail_cleanup_once(lease, terminal)
                .await
        })
    }

    fn confirm_cleanup<'a>(&'a self, lease: &'a StartLease) -> LifecycleFuture<'a> {
        Box::pin(async move { self.app.state::<TaskState>().confirm_cleanup(lease).await })
    }

    fn own_cleanup_observer<'a>(
        &'a self,
        lease: &'a StartLease,
        observer: JoinHandle<()>,
    ) -> LifecycleFuture<'a> {
        Box::pin(async move {
            self.app
                .state::<TaskState>()
                .own_cleanup_observer(lease, observer)
                .await
        })
    }
}
