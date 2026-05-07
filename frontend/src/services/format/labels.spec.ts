import { describe, expect, it } from 'vitest'
import { resolvePrimaryMode } from './labels'

describe('resolvePrimaryMode', () => {
  it('returns frame_interpolation when interpolation is enabled', () => {
    const item = {
      workflowConfig: {
        interpolation: { enabled: true },
        superResolution: { enabled: false },
        anime: { enabled: false },
      },
    } as any
    expect(resolvePrimaryMode(item)).toBe('frame_interpolation')
  })

  it('returns super_resolution when only sr is enabled', () => {
    const item = {
      workflowConfig: {
        interpolation: { enabled: false },
        superResolution: { enabled: true },
        anime: { enabled: false },
      },
    } as any
    expect(resolvePrimaryMode(item)).toBe('super_resolution')
  })

  it('returns anime_optimization when only anime is enabled', () => {
    const item = {
      workflowConfig: {
        interpolation: { enabled: false },
        superResolution: { enabled: false },
        anime: { enabled: true },
      },
    } as any
    expect(resolvePrimaryMode(item)).toBe('anime_optimization')
  })

  it('returns format_conversion when nothing is enabled', () => {
    const item = {
      workflowConfig: {
        interpolation: { enabled: false },
        superResolution: { enabled: false },
        anime: { enabled: false },
      },
    } as any
    expect(resolvePrimaryMode(item)).toBe('format_conversion')
  })
})
