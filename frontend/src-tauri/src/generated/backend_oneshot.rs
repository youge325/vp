// Generated from contracts/ipc-manifest.json. Do not edit.

use std::time::Duration;

use crate::generated::backend_task_envelope::BackendTaskEnvelope;
use crate::models::task::ResumeMode;
use crate::models::{
    EnvironmentCheckResult, ResumeInspectionResult, RuntimeConfigBundle, VideoInfo,
};

pub(crate) const NDJSON_LINE_LIMIT_BYTES: usize = 1048576;
pub(crate) const ONE_SHOT_STDOUT_LIMIT_BYTES: usize = 8388608;
pub(crate) const STDERR_TAIL_LIMIT_BYTES: usize = 65536;
pub(crate) const ERROR_SUMMARY_LIMIT_BYTES: usize = 8192;

mod private {
    pub(crate) trait Sealed {}
}

#[derive(serde::Serialize)]
pub(crate) enum NoStdinPayload {}

pub(crate) trait BackendCommandSpec: private::Sealed {
    type Invocation;
    const SUBCOMMAND: &'static str;
    fn arguments(invocation: &Self::Invocation) -> Vec<String>;
}

pub(crate) trait BackendProcessSpec: BackendCommandSpec {
    type Input: serde::Serialize;
    type Event;

    const STDIN_TIMEOUT: Duration;
    const TERMINATION_TIMEOUT: Duration;
    fn stdin_payload(invocation: &Self::Invocation) -> &Self::Input;
}

pub(crate) trait BackendOneShotSpec: BackendCommandSpec {
    type Input: serde::Serialize;
    type Output;

    const ENVELOPE: &'static str;
    const PAYLOAD_NAME: &'static str;
    const PRESERVE_DISCRIMINATOR: bool;
    const STDIN_TIMEOUT: Duration;
    const TOTAL_TIMEOUT: Duration;
    const TERMINATION_TIMEOUT: Duration;
    fn stdin_payload(invocation: &Self::Invocation) -> Option<&Self::Input>;
}

fn resume_mode_argument(value: &ResumeMode) -> &'static str {
    match value {
        ResumeMode::Auto => "auto",
        ResumeMode::ForceFresh => "force-fresh",
        ResumeMode::ForceResume => "force-resume",
    }
}

#[doc(hidden)]
pub(crate) struct StartTaskInvocation {
    pub(crate) input_path: String,
    pub(crate) resume_mode: Option<ResumeMode>,
    pub(crate) config: RuntimeConfigBundle,
}

#[doc(hidden)]
pub(crate) struct InspectVideoInvocation {
    pub(crate) input_path: String,
}

#[doc(hidden)]
#[derive(Clone, Copy, Debug, Default)]
pub(crate) struct CheckEnvironmentInvocation;

#[doc(hidden)]
pub(crate) struct CheckResumeStateInvocation {
    pub(crate) input_path: String,
    pub(crate) config: RuntimeConfigBundle,
}

pub(crate) struct StartTaskSpec;

impl private::Sealed for StartTaskSpec {}

impl BackendCommandSpec for StartTaskSpec {
    type Invocation = StartTaskInvocation;
    const SUBCOMMAND: &'static str = "process";

    fn arguments(invocation: &Self::Invocation) -> Vec<String> {
        let mut arguments = vec![
            "--input".to_string(),
            invocation.input_path.clone(),
            "--config-stdin".to_string(),
        ];
        if let Some(value) = &invocation.resume_mode {
            arguments.push("--resume-mode".to_string());
            arguments.push(resume_mode_argument(value).to_string());
        }
        arguments
    }
}

impl BackendProcessSpec for StartTaskSpec {
    type Input = RuntimeConfigBundle;
    type Event = BackendTaskEnvelope;

    const STDIN_TIMEOUT: Duration = Duration::from_millis(10000);
    const TERMINATION_TIMEOUT: Duration = Duration::from_millis(5000);

    fn stdin_payload(invocation: &Self::Invocation) -> &Self::Input {
        &invocation.config
    }
}

pub(crate) struct InspectVideoSpec;

impl private::Sealed for InspectVideoSpec {}

impl BackendCommandSpec for InspectVideoSpec {
    type Invocation = InspectVideoInvocation;
    const SUBCOMMAND: &'static str = "info";

    fn arguments(invocation: &Self::Invocation) -> Vec<String> {
        let arguments = vec!["--input".to_string(), invocation.input_path.clone()];
        arguments
    }
}

impl BackendOneShotSpec for InspectVideoSpec {
    type Input = NoStdinPayload;
    type Output = VideoInfo;

    const ENVELOPE: &'static str = "info";
    const PAYLOAD_NAME: &'static str = "VideoInfo";
    const PRESERVE_DISCRIMINATOR: bool = false;
    const STDIN_TIMEOUT: Duration = Duration::from_millis(10000);
    const TOTAL_TIMEOUT: Duration = Duration::from_millis(30000);
    const TERMINATION_TIMEOUT: Duration = Duration::from_millis(5000);

    fn stdin_payload(_invocation: &Self::Invocation) -> Option<&Self::Input> {
        None
    }
}

pub(crate) struct CheckEnvironmentSpec;

impl private::Sealed for CheckEnvironmentSpec {}

impl BackendCommandSpec for CheckEnvironmentSpec {
    type Invocation = CheckEnvironmentInvocation;
    const SUBCOMMAND: &'static str = "check";

    fn arguments(_invocation: &Self::Invocation) -> Vec<String> {
        Vec::new()
    }
}

impl BackendOneShotSpec for CheckEnvironmentSpec {
    type Input = NoStdinPayload;
    type Output = EnvironmentCheckResult;

    const ENVELOPE: &'static str = "check";
    const PAYLOAD_NAME: &'static str = "EnvironmentCheckResult";
    const PRESERVE_DISCRIMINATOR: bool = false;
    const STDIN_TIMEOUT: Duration = Duration::from_millis(10000);
    const TOTAL_TIMEOUT: Duration = Duration::from_millis(180000);
    const TERMINATION_TIMEOUT: Duration = Duration::from_millis(5000);

    fn stdin_payload(_invocation: &Self::Invocation) -> Option<&Self::Input> {
        None
    }
}

pub(crate) struct CheckResumeStateSpec;

impl private::Sealed for CheckResumeStateSpec {}

impl BackendCommandSpec for CheckResumeStateSpec {
    type Invocation = CheckResumeStateInvocation;
    const SUBCOMMAND: &'static str = "inspect-output";

    fn arguments(invocation: &Self::Invocation) -> Vec<String> {
        let arguments = vec![
            "--input".to_string(),
            invocation.input_path.clone(),
            "--config-stdin".to_string(),
        ];
        arguments
    }
}

impl BackendOneShotSpec for CheckResumeStateSpec {
    type Input = RuntimeConfigBundle;
    type Output = ResumeInspectionResult;

    const ENVELOPE: &'static str = "resume_inspection";
    const PAYLOAD_NAME: &'static str = "ResumeInspectionResult";
    const PRESERVE_DISCRIMINATOR: bool = true;
    const STDIN_TIMEOUT: Duration = Duration::from_millis(10000);
    const TOTAL_TIMEOUT: Duration = Duration::from_millis(60000);
    const TERMINATION_TIMEOUT: Duration = Duration::from_millis(5000);

    fn stdin_payload(invocation: &Self::Invocation) -> Option<&Self::Input> {
        Some(&invocation.config)
    }
}
