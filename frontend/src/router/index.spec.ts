import { beforeEach, describe, expect, it } from 'vitest'
import { WORKBENCH_STAGES, WORKFLOW_STEPS } from '@/lib/workflow'
import { router } from '@/router'

describe('workflow routes', () => {
  beforeEach(async () => {
    await router.push('/prepare')
  })

  it('groups the workbench into four primary stages', () => {
    expect(WORKBENCH_STAGES).toHaveLength(4)
    expect(WORKBENCH_STAGES.map((stage) => stage.title)).toEqual([
      '准备',
      '增强',
      '交付',
      '结果',
    ])
  })

  it('keeps the legacy eight-step mapping', () => {
    expect(WORKFLOW_STEPS).toHaveLength(8)
    expect(WORKFLOW_STEPS.map((step) => step.title)).toEqual([
      '环境',
      '输入',
      '补帧',
      '超分',
      '动漫',
      '编解码',
      '运行',
      '日志',
    ])
  })

  it('redirects legacy paths into the new stage routes', async () => {
    const redirects = [
      ['/overview', '/prepare'],
      ['/source', '/prepare?tab=input'],
      ['/interpolation', '/enhance?section=interpolation'],
      ['/super-resolution', '/enhance?section=super-resolution'],
      ['/anime', '/enhance?section=anime'],
      ['/format', '/deliver'],
      ['/preview', '/results'],
    ] as const

    for (const [from, to] of redirects) {
      await router.push(from)
      expect(router.currentRoute.value.fullPath).toBe(to)
    }
  })
})
