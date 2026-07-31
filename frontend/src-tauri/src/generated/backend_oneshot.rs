// Generated from contracts/ipc-manifest.json. Do not edit.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) struct BackendOneShotContract {
    pub(crate) subcommand: &'static str,
    pub(crate) envelope: &'static str,
    pub(crate) preserve_discriminator: bool,
}

pub(crate) fn backend_oneshot_contract(ipc_command: &str) -> Option<BackendOneShotContract> {
    match ipc_command {
        "inspect_video" => Some(BackendOneShotContract {
            subcommand: "info",
            envelope: "info",
            preserve_discriminator: false,
        }),
        "check_environment" => Some(BackendOneShotContract {
            subcommand: "check",
            envelope: "check",
            preserve_discriminator: false,
        }),
        "check_resume_state" => Some(BackendOneShotContract {
            subcommand: "inspect-output",
            envelope: "resume_inspection",
            preserve_discriminator: true,
        }),
        _ => None,
    }
}
