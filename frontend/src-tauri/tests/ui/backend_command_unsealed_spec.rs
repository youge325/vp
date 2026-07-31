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

struct ArbitraryCommand;
struct ArbitraryInvocation;

impl backend_oneshot::BackendCommandSpec for ArbitraryCommand {
    type Invocation = ArbitraryInvocation;
    const SUBCOMMAND: &'static str = "arbitrary";

    fn arguments(_invocation: &Self::Invocation) -> Vec<String> {
        Vec::new()
    }
}

fn main() {}
