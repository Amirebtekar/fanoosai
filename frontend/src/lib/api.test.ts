import { describe, expect, it } from 'vitest'
import { ApiError, getErrorMessage } from './api'

describe('getErrorMessage', () => {
  it('returns fallback for unknown errors', () => {
    expect(getErrorMessage(null, 'fallback')).toBe('fallback')
  })

  it('returns message from regular Error', () => {
    expect(getErrorMessage(new Error('network timeout'), 'fallback')).toBe('network timeout')
  })

  it('returns Persian message from Error', () => {
    expect(getErrorMessage(new Error('همه مدل‌ها امروز اجرا شده‌اند.'), 'fallback')).toBe('همه مدل‌ها امروز اجرا شده‌اند.')
  })

  it('returns string detail from ApiError', () => {
    expect(getErrorMessage(new ApiError(400, 'bad request'), 'fallback')).toBe('bad request')
  })

  it('returns nested detail from ApiError', () => {
    expect(getErrorMessage(new ApiError(400, { detail: 'inner' }), 'fallback')).toBe('inner')
  })

  it('returns reason from nested object detail', () => {
    expect(getErrorMessage(new ApiError(400, { detail: { reason: 'why' } }), 'fallback')).toBe('why')
  })

  it('falls back to message when ApiError detail is object without extractable string', () => {
    expect(getErrorMessage(new ApiError(500, { foo: 1 }), 'fallback')).toBe('[object Object]')
  })
})
