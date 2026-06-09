// IPC endpoints — 任务启动、控制与续跑探测。

import type { TaskRequest } from '@/types/protocol'
import type { ResumeInspectionResult } from '@/types/domain/batch'
import { safeInvoke } from '../client'

export const taskIpc = {
  start(request: TaskRequest): Promise<void> {
    return safeInvoke('start_task', { request })
  },
  checkResume(request: TaskRequest): Promise<ResumeInspectionResult> {
    return safeInvoke('check_resume_state', { request })
  },
  cancel(): Promise<void> {
    return safeInvoke('cancel_task')
  },
  pause(): Promise<void> {
    return safeInvoke('control_task', { kind: 'pause' })
  },
  resume(): Promise<void> {
    return safeInvoke('control_task', { kind: 'resume' })
  },
  openOutputLocation(path: string): Promise<void> {
    return safeInvoke('open_output_location', { path })
  },
}
