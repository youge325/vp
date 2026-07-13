// pure: no Vue / no Pinia / no Tauri
// Resume 冲突分类与 wire/error payload 到领域 descriptor 的投影。

import type { TaskError } from '@/types/domain/media'
import type { ResumeConflictDescriptor } from '@/types/domain/batch'
import type { ResumeInspectionResult } from '@/types/protocol'

interface ResumeConflictSource {
  outputPath: string
  signatureMatch: boolean
  completedChunks: number
  completedOutputFrames: number
  totalOutputFrames: number
}

function createResumeConflictDescriptor(source: ResumeConflictSource): ResumeConflictDescriptor {
  return {
    kind: source.signatureMatch && source.completedChunks > 0
      ? 'final_exists_with_resume'
      : 'final_exists_only',
    outputPath: source.outputPath,
    progress: {
      completedChunks: source.completedChunks,
      completedOutputFrames: source.completedOutputFrames,
      totalOutputFrames: source.totalOutputFrames,
    },
  }
}

export function buildResumeConflictDescriptor(
  inspection: ResumeInspectionResult,
): ResumeConflictDescriptor | null {
  if (!inspection.finalExists) {
    return null
  }
  return createResumeConflictDescriptor(inspection)
}

export function buildResumeConflictDescriptorFromError(error: TaskError): ResumeConflictDescriptor {
  const details = (error.details ?? {}) as Record<string, unknown>
  return createResumeConflictDescriptor({
    outputPath: typeof details.outputPath === 'string' ? details.outputPath : '',
    signatureMatch: Boolean(details.sidecarSignatureMatch),
    completedChunks: Number(details.completedChunks ?? 0),
    completedOutputFrames: Number(details.completedOutputFrames ?? 0),
    totalOutputFrames: 0,
  })
}
