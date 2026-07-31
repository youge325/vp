import { describe, expect, it } from 'vitest'
import { normalizeError } from '@/lib/errors/normalize'

describe('normalizeError', () => {
  it('returns the error as-is when it already has code and message', () => {
    const error = { code: 'test_error', message: 'Something went wrong.', details: null }
    expect(normalizeError(error)).toEqual(error)
  })

  it('wraps a plain Error instance', () => {
    const error = new Error('Plain error')
    expect(normalizeError(error)).toEqual({
      code: 'process_failed',
      message: 'Plain error',
      details: null,
    })
  })

  it('wraps an unknown value with an explicit fallback code', () => {
    expect(normalizeError('oops', 'persistence_failed')).toEqual({
      code: 'persistence_failed',
      message: 'oops',
      details: null,
    })
  })

  it('uses default code (process_failed) when fallback is not provided', () => {
    expect(normalizeError(42)).toEqual({
      code: 'process_failed',
      message: '42',
      details: null,
    })
  })

  it('preserves details object when present on the shell payload', () => {
    const error = {
      code: 'persistence_failed',
      message: 'disk full',
      details: { path: '/var/log/foo' },
    }
    expect(normalizeError(error)).toEqual(error)
  })
})
