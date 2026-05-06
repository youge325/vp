// IPC endpoints — 任务启动、控制与续跑探测。

import type { TaskRequest } from '@/types/protocol'
import type { ResumeInspectionResult } from '@/types/domain/batch'
import { safeInvoke } from '../client'

export const taskIpc = {
  start(request: TaskRequest): Promise<void> {
    return safeInvoke<void>('start_task', { request })
  },
  checkResume(request: TaskRequest): Promise<ResumeInspectionResult> {
    return safeInvoke<ResumeInspectionResult>('check_resume_state', { request })
  },
  cancel(): Promise<void> {
    return safeInvoke<void>('cancel_task')
  },
  pause(): Promise<void> {
    return safeInvoke<void>('pause_task')
  },
  resume(): Promise<void> {
    return safeInvoke<void>('resume_task')
  },
  openOutputLocation(path: string): Promise<void> {
    return safeInvoke<void>('open_output_location', { path })
  },
}
