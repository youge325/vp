// Compile-only checks for the typed IPC command contract.
//
// This file is included by ``tsconfig.app.json`` but is not imported by
// runtime code. It intentionally exercises representative ``safeInvoke`` calls
// so command names, argument objects and return types are checked by vue-tsc.

import { safeInvoke } from './client'
import type { VideoInfoResult } from '@/types/domain/media'
import type {
  EnvironmentCheckPayload,
  ResumeInspectionResult,
  TaskRequest,
  WorkbenchPreset,
} from '@/types/protocol'

async function checkTypedInvokeContract(
  request: TaskRequest,
  preset: WorkbenchPreset,
): Promise<void> {
  const inputs: string[] = await safeInvoke('pick_inputs')
  const outputDir: string | null = await safeInvoke('pick_output_directory')
  const environment: EnvironmentCheckPayload = await safeInvoke('check_environment', { forceRefresh: true })
  const loadedPreset: WorkbenchPreset | null = await safeInvoke('load_workbench_preset')
  const videoInfo: VideoInfoResult = await safeInvoke('inspect_video', { inputPath: 'D:/in.mp4' })
  const resumeInspection: ResumeInspectionResult = await safeInvoke('check_resume_state', { request })

  await safeInvoke('save_workbench_preset', { preset })
  await safeInvoke('start_task', { request })
  await safeInvoke('cancel_task')
  await safeInvoke('control_task', { kind: 'pause' })
  await safeInvoke('control_task', { kind: 'resume' })
  await safeInvoke('open_output_location', { path: 'D:/out/out.mp4' })

  void inputs
  void outputDir
  void environment
  void loadedPreset
  void videoInfo
  void resumeInspection
}

void checkTypedInvokeContract
