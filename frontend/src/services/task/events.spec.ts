import { describe, expect, it } from 'vitest'
import { appendTaskLog, classifyTaskLogLine, createIdleTaskState, displayTaskLogLine } from './events'

function appendLine(logs: string[], message: string): string[] {
  return appendTaskLog({ ...createIdleTaskState(), logs }, { message }).logs
}

describe('appendTaskLog', () => {
  it('keeps separate progress lines for different stages', () => {
    const stage1 = '[VP_PROGRESS] [1/2 01_frame_interpolation] 100.0% 2/2'
    const stage2 = '[VP_PROGRESS] [2/2 02_super_resolution]   0.0% 0/5'

    const logs = appendLine([stage1], stage2)

    expect(logs).toEqual([stage1, stage2])
  })

  it('replaces the matching stage progress line in place', () => {
    const oldStage1 = '[VP_PROGRESS] [1/2 01_frame_interpolation]  50.0% 1/2'
    const stage2 = '[VP_PROGRESS] [2/2 02_super_resolution]   0.0% 0/5'
    const nextStage1 = '[VP_PROGRESS] [1/2 01_frame_interpolation] 100.0% 2/2'

    const logs = appendLine([oldStage1, stage2], nextStage1)

    expect(logs).toEqual([nextStage1, stage2])
  })

  it('keeps legacy unkeyed progress replacement behavior', () => {
    const logs = appendLine(['regular log', '[VP_PROGRESS] 10%'], '[VP_PROGRESS] 20%')

    expect(logs).toEqual(['regular log', '[VP_PROGRESS] 20%'])
  })

  it('keeps TensorRT lifecycle logs as ordinary append-only lines', () => {
    const buildLine =
      '22:03:13 [INFO] app.algorithms.paddle.paddlegan_vsr.runner: ' +
      '[VP_TRT] TensorRT BUILD PaddleGAN ppmsvsr shape=1x5x3x288x640'
    const readyLine =
      '22:03:14 [INFO] app.algorithms.paddle.paddlegan_vsr.runner: [VP_TRT] TensorRT READY outputs=output'
    const logs = appendLine(
      ['regular log', buildLine],
      readyLine,
    )

    expect(logs).toEqual([
      'regular log',
      buildLine,
      readyLine,
    ])
  })
})

describe('classifyTaskLogLine', () => {
  it('classifies progress, TensorRT, and default log lines', () => {
    expect(classifyTaskLogLine('[VP_PROGRESS] [1/2 stage] 10%')).toBe('progress')
    expect(
      classifyTaskLogLine(
        '22:03:13 [INFO] app.algorithms.paddle.paddlegan_vsr.runner: ' +
          '[VP_TRT] TensorRT BUILD PaddleGAN ppmsvsr shape=1x5x3x288x640',
      ),
    ).toBe('tensorrt')
    expect(classifyTaskLogLine('plain backend stderr')).toBe('default')
  })
})

describe('displayTaskLogLine', () => {
  it('removes the internal TensorRT marker while preserving the logging prefix', () => {
    const line =
      '22:03:13 [INFO] app.algorithms.paddle.paddlegan_vsr.runner: ' +
      '[VP_TRT] TensorRT LOAD static_model=model.json params=model.pdiparams'

    expect(displayTaskLogLine(line)).toBe(
      '22:03:13 [INFO] app.algorithms.paddle.paddlegan_vsr.runner: ' +
        'TensorRT LOAD static_model=model.json params=model.pdiparams',
    )
  })
})
