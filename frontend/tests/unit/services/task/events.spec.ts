import { describe, expect, it } from 'vitest'
import * as taskEvents from '@/services/task/events'
import { appendTaskLog, createIdleTaskState, displayTaskLogLine } from '@/services/task/events'

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

  it('moves the matching stage progress line to the tail', () => {
    const oldStage1 = '[VP_PROGRESS] [1/2 01_frame_interpolation]  50.0% 1/2'
    const stage2 = '[VP_PROGRESS] [2/2 02_super_resolution]   0.0% 0/5'
    const nextStage1 = '[VP_PROGRESS] [1/2 01_frame_interpolation] 100.0% 2/2'

    const logs = appendLine([oldStage1, stage2], nextStage1)

    expect(logs).toEqual([stage2, nextStage1])
  })

  it('keeps the latest matching stage progress after later lifecycle logs', () => {
    const oldProgress = '[VP_PROGRESS] [1/2 01_super_resolution] [------------------------] 0.0% 0/6723'
    const tensorRtLog =
      '22:03:49 [INFO] app.algorithms.paddle.paddlegan_vsr.runner: ' +
      '[VP_TRT] TensorRT READY outputs=fetch_name_0,fetch_name_1'
    const plainLog = '22:03:50 [INFO] app.utils.ffmpeg: muxer ready'
    const nextProgress = '[VP_PROGRESS] [1/2 01_super_resolution] [#-----------------------] 2.5% 165/6723'

    const logs = appendLine([oldProgress, tensorRtLog, plainLog], nextProgress)

    expect(logs).toEqual([tensorRtLog, plainLog, nextProgress])
  })

  it('inserts later lifecycle logs before trailing progress lines', () => {
    const progress = '[VP_PROGRESS] [1/2 01_super_resolution] [------------------------] 0.0% 0/6723'
    const tensorRtLog =
      '22:03:49 [INFO] app.algorithms.paddle.paddlegan_vsr.runner: ' +
      '[VP_TRT] TensorRT LOAD static_model=model.json params=model.pdiparams'

    const logs = appendLine(['regular log', progress], tensorRtLog)

    expect(logs).toEqual(['regular log', tensorRtLog, progress])
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

describe('task event public surface', () => {
  it('keeps log classification private to the task event reducer', () => {
    expect('classifyTaskLogLine' in taskEvents).toBe(false)
  })
})

describe('displayTaskLogLine', () => {
  it('leaves regular and progress logs unchanged', () => {
    expect(displayTaskLogLine('plain backend stderr')).toBe('plain backend stderr')
    expect(displayTaskLogLine('[VP_PROGRESS] [1/2 stage] 10%')).toBe('[VP_PROGRESS] [1/2 stage] 10%')
  })

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
