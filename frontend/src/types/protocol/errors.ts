// 前端生产代码实际消费的错误码运行时别名。
// 完整集合由 Rust `TaskErrorCode` 生成；这里的值通过 `satisfies` 校验。

import type { TaskErrorCode } from '@/types/generated/contracts'

export const TASK_ERROR_CODES = {
  ProcessFailed: 'process_failed',
  ResumeConflict: 'resume_conflict',
  IoError: 'io_error',
  SchemaMismatch: 'schema_mismatch',
  PersistenceFailed: 'persistence_failed',
} as const satisfies Record<string, TaskErrorCode>

export type { TaskErrorCode }
