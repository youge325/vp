import { describe, expect, it } from 'vitest'

import { seedProfileOptions, updateProfileOption } from './options'
import type { CapabilityOptionSpec } from '@/types/domain/capability'

const option = (
  name: string,
  type: CapabilityOptionSpec['type'],
  overrides: Partial<CapabilityOptionSpec> = {},
): CapabilityOptionSpec => ({
  name,
  label: name,
  type,
  defaultValue: null,
  choices: [],
  min: null,
  max: null,
  ...overrides,
})

describe('preset option rules', () => {
  it('seeds only supported profile options while preserving existing values', () => {
    const options = seedProfileOptions(
      {
        options: [
          option('preset', 'choice', {
            defaultValue: 'slow',
            choices: [
              { label: 'Medium', value: 'medium' },
              { label: 'Slow', value: 'slow' },
            ],
          }),
          option('lookahead', 'number', {
            choices: [{ label: '16', value: 16 }],
          }),
          option('aq', 'boolean'),
          option('tune', 'string'),
        ],
      },
      {
        preset: 'medium',
        stale: true,
      },
    )

    expect(options).toEqual({
      preset: 'medium',
      lookahead: 16,
      aq: false,
      tune: '',
    })
  })

  it('returns an empty option map when no profile is selected', () => {
    expect(seedProfileOptions(null, { preset: 'slow' })).toEqual({})
  })

  it('updates profile options without mutating the previous map', () => {
    const previous = { preset: 'medium' }
    const next = updateProfileOption(previous, 'preset', 'slow')

    expect(next).toEqual({ preset: 'slow' })
    expect(previous).toEqual({ preset: 'medium' })
  })
})
