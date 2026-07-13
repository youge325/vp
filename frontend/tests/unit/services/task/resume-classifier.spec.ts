import { describe, expect, it } from 'vitest'

import {
  buildResumeConflictDescriptor,
  buildResumeConflictDescriptorFromError,
} from '@/services/task/resume-classifier'
import type { TaskError } from '@/types/domain/media'

describe('resume conflict classification', () => {
  it('classifies final output with resumable chunks', () => {
    expect(buildResumeConflictDescriptor({
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
    })).toEqual({
      kind: 'final_exists_with_resume',
      outputPath: 'D:/out.mp4',
      progress: {
        completedChunks: 2,
        completedOutputFrames: 120,
        totalOutputFrames: 240,
      },
    })
  })

  it('projects error details without fabricating an inspection wire payload', () => {
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

    expect(buildResumeConflictDescriptorFromError(error)).toEqual({
      kind: 'final_exists_with_resume',
      outputPath: 'D:/out.mp4',
      progress: {
        completedChunks: 2,
        completedOutputFrames: 120,
        totalOutputFrames: 0,
      },
    })
  })

  it('does not offer resume when a matching sidecar has no completed chunks', () => {
    expect(buildResumeConflictDescriptorFromError({
      code: 'resume_conflict',
      message: 'resume conflict',
      details: {
        outputPath: 'D:/out.mp4',
        sidecarSignatureMatch: true,
        completedChunks: 0,
        completedOutputFrames: 0,
      },
    }).kind).toBe('final_exists_only')
  })
})
