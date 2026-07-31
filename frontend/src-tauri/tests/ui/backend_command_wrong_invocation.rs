mod generated {
    pub(crate) mod backend_task_envelope {
        pub(crate) struct BackendTaskEnvelope;
    }
}

mod models {
    pub(crate) struct EnvironmentCheckResult;
    pub(crate) struct ResumeInspectionResult;
    pub(crate) struct VideoInfo;

    #[derive(serde::Serialize)]
    pub(crate) struct RuntimeConfigBundle;

    pub(crate) mod task {
        pub(crate) enum ResumeMode {
            Auto,
            ForceFresh,
            ForceResume,
        }
    }
}

#[path = "../../src/generated/backend_oneshot.rs"]
mod backend_oneshot;

use backend_oneshot::{
    BackendCommandSpec, CheckEnvironmentInvocation, InspectVideoSpec,
};

fn accepts_invocation<S: BackendCommandSpec>(_invocation: S::Invocation) {}

fn main() {
    accepts_invocation::<InspectVideoSpec>(CheckEnvironmentInvocation);
}
