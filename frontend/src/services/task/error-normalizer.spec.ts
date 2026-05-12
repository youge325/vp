import { describe, expect, it } from 'vitest'
import { normalizeTaskError } from './error-normalizer'

describe('normalizeTaskError', () => {
  it('returns the error as-is when it already has code and message', () => {
    const error = { code: 'test_error', message: 'Something went wrong.', details: null }
    expect(normalizeTaskError(error)).toEqual(error)
  })

  it('wraps a plain Error instance', () => {
    const error = new Error('Plain error')
    expect(normalizeTaskError(error)).toEqual({
      code: 'process_failed',
      message: 'Plain error',
      details: null,
    })
  })

  it('wraps an unknown value with a custom fallback code', () => {
    expect(normalizeTaskError('oops', 'custom_code')).toEqual({
      code: 'custom_code',
      message: 'oops',
      details: null,
    })
  })

  it('uses default code (process_failed) when fallback is not provided', () => {
    expect(normalizeTaskError(42)).toEqual({
      code: 'process_failed',
      message: '42',
      details: null,
    })
  })
})
