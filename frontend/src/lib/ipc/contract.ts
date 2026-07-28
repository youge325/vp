/* Generated from contracts/ipc-manifest.json. Do not edit. */

import type {
  EnvironmentCheckPayload,
  ResumeInspectionResult,
  TaskControlKind,
  TaskRequest,
  VideoInfo,
  WorkbenchPreset,
} from '@/types/protocol'

interface IpcCommandArgs {
  pick_inputs: undefined
  pick_output_directory: undefined
  check_environment: { forceRefresh: boolean }
  load_workbench_preset: undefined
  save_workbench_preset: { preset: WorkbenchPreset }
  inspect_video: { inputPath: string }
  check_resume_state: { request: TaskRequest }
  start_task: { request: TaskRequest }
  control_task: { kind: TaskControlKind }
  open_output_location: { path: string }
}

export type IpcCommand = keyof IpcCommandArgs

interface IpcCommandResult {
  pick_inputs: string[]
  pick_output_directory: string|null
  check_environment: EnvironmentCheckPayload
  load_workbench_preset: WorkbenchPreset|null
  save_workbench_preset: void
  inspect_video: VideoInfo
  check_resume_state: ResumeInspectionResult
  start_task: void
  control_task: void
  open_output_location: void
}

export type IpcInvokeArgs<C extends IpcCommand> = IpcCommandArgs[C]
export type IpcInvokeResult<C extends IpcCommand> = IpcCommandResult[C]
