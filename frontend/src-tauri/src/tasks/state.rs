use tokio::sync::{mpsc, oneshot, Mutex};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TaskControlKind {
    Cancel,
    Pause,
    Resume,
}

pub struct TaskControlMessage {
    pub kind: TaskControlKind,
    pub response: oneshot::Sender<Result<(), String>>,
}

#[derive(Clone)]
pub struct RunningTask {
    pub control_tx: mpsc::Sender<TaskControlMessage>,
}

#[derive(Default)]
pub struct TaskState {
    pub current: Mutex<Option<RunningTask>>,
}
