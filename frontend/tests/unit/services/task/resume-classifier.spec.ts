import { describe, expect, it } from 'vitest'

import { buildInspectionFromError, classifyResumeConflict } from '@/services/task/resume-classifier'
import type { TaskError } from '@/types/domain/media'

describe('resume conflict classification', () => {
  it('classifies final output with resumable chunks', () => {
    expect(classifyResumeConflict({
      type: 'resume_inspection',
      pipeline_kind: 'streaming',
      outputPath: 'D:/out.mp4',
      input_path: 'D:/in.mp4',
      finalExists: true,
      sidecarExists: true,
      signatureMatch: true,
      completedChunks: 2,
      completedOutputFrames: 120,
      nextSourceFrame: 60,
      totalOutputFrames: 240,
    })).toBe('final_exists_with_resume')
  })

  it('rebuilds the generated inspection wire shape from error details', () => {
    const error: TaskError = {
      code: 'resume_conflict',
      message: 'resume conflict',
      details: {
        outputPath: 'D:/out.mp4',
        inputPath: 'D:/in.mp4',
        sidecarSignatureMatch: true,
        completedChunks: 2,
        completedOutputFrames: 120,
      },
    }

    expect(buildInspectionFromError(error, 'D:/fallback.mp4')).toEqual({
      type: 'resume_inspection',
      pipeline_kind: 'streaming',
      outputPath: 'D:/out.mp4',
      input_path: 'D:/in.mp4',
      finalExists: true,
      sidecarExists: true,
      signatureMatch: true,
      completedChunks: 2,
      completedOutputFrames: 120,
      nextSourceFrame: 0,
      totalOutputFrames: 0,
    })
  })
})
