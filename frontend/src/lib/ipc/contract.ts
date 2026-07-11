// IPC command contract — compile-time mapping for Tauri invoke calls.
//
// The Rust command surface still lives in
// ``frontend/src-tauri/src/commands_manifest.rs``. This file mirrors that
// surface on the TypeScript side so ``safeInvoke`` can infer the required
// argument object and return type from the command name.

import type { ResumeInspectionResult } from '@/types/domain/batch'
import type { EnvironmentCheckPayload } from '@/types/protocol'
import type { VideoInfoResult } from '@/types/domain/media'
import type { TaskRequest, WorkbenchPreset } from '@/types/protocol'

type TaskControlKind = 'pause' | 'resume'

interface IpcCommandArgs {
  pick_inputs: undefined
  pick_output_directory: undefined
  check_environment: { forceRefresh: boolean }
  load_workbench_preset: undefined
  save_workbench_preset: { preset: WorkbenchPreset }
  inspect_video: { inputPath: string }
  check_resume_state: { request: TaskRequest }
  start_task: { request: TaskRequest }
  cancel_task: undefined
  control_task: { kind: TaskControlKind }
  open_output_location: { path: string }
}

export type IpcCommand = keyof IpcCommandArgs

interface IpcCommandResult {
  pick_inputs: string[]
  pick_output_directory: string | null
  check_environment: EnvironmentCheckPayload
  load_workbench_preset: WorkbenchPreset | null
  save_workbench_preset: void
  inspect_video: VideoInfoResult
  check_resume_state: ResumeInspectionResult
  start_task: void
  cancel_task: void
  control_task: void
  open_output_location: void
}

export type IpcInvokeArgs<C extends IpcCommand> = IpcCommandArgs[C]
export type IpcInvokeResult<C extends IpcCommand> = IpcCommandResult[C]

type _ResultsCoverEveryCommand =
  keyof IpcCommandResult extends IpcCommand
    ? IpcCommand extends keyof IpcCommandResult ? true : never
    : never

const _RESULTS_COVERAGE_CHECK: _ResultsCoverEveryCommand = true
void _RESULTS_COVERAGE_CHECK
