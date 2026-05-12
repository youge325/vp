use tokio::sync::{oneshot, Mutex};

use crate::tasks::handle::TaskHandle;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TaskControlKind {
    Pause,
    Resume,
}

pub struct TaskControlMessage {
    pub kind: TaskControlKind,
    pub response: oneshot::Sender<Result<(), String>>,
}

#[derive(Default)]
pub struct TaskState {
    pub current: Mutex<Option<TaskHandle>>,
}
