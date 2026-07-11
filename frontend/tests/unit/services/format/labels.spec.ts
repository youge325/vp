import { describe, expect, it } from 'vitest'
import * as labelModule from '@/services/format/labels'
import { getWorkflowSummaryLabel } from '@/services/format/labels'

function itemWithWorkflow({
  interpolation = false,
  superResolution = false,
  anime = false,
}: {
  interpolation?: boolean
  superResolution?: boolean
  anime?: boolean
}) {
  return {
    workflowConfig: {
      interpolation: { enabled: interpolation },
      superResolution: { enabled: superResolution },
      anime: { enabled: anime },
    },
  } as any
}

describe('getWorkflowSummaryLabel', () => {
  it('keeps primary mode resolution private to label formatting', () => {
    expect('resolvePrimaryMode' in labelModule).toBe(false)
  })

  it('returns the interpolation summary when interpolation is enabled', () => {
    expect(getWorkflowSummaryLabel(itemWithWorkflow({ interpolation: true }))).toBe('补帧')
  })

  it('returns the super-resolution summary when only super-resolution is enabled', () => {
    expect(getWorkflowSummaryLabel(itemWithWorkflow({ superResolution: true }))).toBe('超分')
  })

  it('returns the anime summary when only anime optimization is enabled', () => {
    expect(getWorkflowSummaryLabel(itemWithWorkflow({ anime: true }))).toBe('动漫')
  })

  it('returns the conversion summary when no enhancement is enabled', () => {
    expect(getWorkflowSummaryLabel(itemWithWorkflow({}))).toBe('转码')
  })

  it('joins enabled enhancement labels in workflow order', () => {
    expect(
      getWorkflowSummaryLabel(itemWithWorkflow({ interpolation: true, superResolution: true, anime: true })),
    ).toBe('补帧 / 超分 / 动漫')
  })
})
