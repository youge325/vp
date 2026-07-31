import { describe, expect, it } from 'vitest'
import { getWorkflowSummaryLabel } from '@/services/format/labels'
import { createDefaultWorkflowConfigForEnvironment } from '@/services/preset/workflow-defaults'

function workflowWithEnhancements({
  interpolation = false,
  superResolution = false,
}: {
  interpolation?: boolean
  superResolution?: boolean
}) {
  const workflowConfig = createDefaultWorkflowConfigForEnvironment(null)
  workflowConfig.interpolation.enabled = interpolation
  workflowConfig.superResolution.enabled = superResolution
  return workflowConfig
}

describe('getWorkflowSummaryLabel', () => {
  it('returns the interpolation summary when interpolation is enabled', () => {
    expect(getWorkflowSummaryLabel(workflowWithEnhancements({ interpolation: true }))).toBe('补帧')
  })

  it('returns the super-resolution summary when only super-resolution is enabled', () => {
    expect(getWorkflowSummaryLabel(workflowWithEnhancements({ superResolution: true }))).toBe('超分')
  })

  it('returns the conversion summary when no enhancement is enabled', () => {
    expect(getWorkflowSummaryLabel(workflowWithEnhancements({}))).toBe('转码')
  })

  it('joins enabled enhancement labels in workflow order', () => {
    expect(
      getWorkflowSummaryLabel(workflowWithEnhancements({ interpolation: true, superResolution: true })),
    ).toBe('补帧 / 超分')
  })
})
