// pure: no Vue / no Pinia / no Tauri
// Resume 冲突分类与从错误 details 重建 inspection 结构。

import type { TaskError } from '@/types/domain/media'
import type { ResumeConflictKind, ResumeInspectionResult } from '@/types/domain/batch'

export function classifyResumeConflict(inspection: ResumeInspectionResult): ResumeConflictKind | null {
  if (!inspection.finalExists) {
    return null
  }
  if (inspection.signatureMatch && inspection.completedChunks > 0) {
    return 'final_exists_with_resume'
  }
  return 'final_exists_only'
}

export function buildInspectionFromError(
  error: TaskError,
  fallbackInputPath: string,
): ResumeInspectionResult {
  const details = (error.details ?? {}) as Record<string, unknown>
  return {
    type: 'resume_inspection',
    pipeline_kind: 'streaming',
    outputPath: typeof details.outputPath === 'string' ? details.outputPath : '',
    inputPath: typeof details.inputPath === 'string' ? details.inputPath : fallbackInputPath,
    finalExists: true,
    sidecarExists: Boolean(details.sidecarSignatureMatch),
    signatureMatch: Boolean(details.sidecarSignatureMatch),
    completedChunks: Number(details.completedChunks ?? 0),
    completedOutputFrames: Number(details.completedOutputFrames ?? 0),
    nextSourceFrame: 0,
    totalOutputFrames: 0,
  }
}
