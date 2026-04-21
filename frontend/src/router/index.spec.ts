import { describe, expect, it } from 'vitest'
import { WORKFLOW_STEPS } from '@/lib/workflow'

describe('workflow routes', () => {
  it('keeps the planned eight-step structure', () => {
    expect(WORKFLOW_STEPS).toHaveLength(8)
    expect(WORKFLOW_STEPS.map((step) => step.title)).toEqual([
      '概览',
      '素材',
      '视频补帧',
      '超分辨率',
      '动漫优化',
      '格式转换',
      '输出与执行',
      '结果预览',
    ])
  })
})
