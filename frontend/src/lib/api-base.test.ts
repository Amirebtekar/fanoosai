import { afterEach, describe, expect, it, vi } from 'vitest'
import { getApiBaseUrl } from './api-base'

describe('getApiBaseUrl', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('uses window.location.origin when no URL is configured', () => {
    vi.stubGlobal('window', { location: { origin: 'https://fanoos.amirebtekar.ir' } })
    expect(getApiBaseUrl()).toBe('https://fanoos.amirebtekar.ir')
  })

  it('returns empty string when window is unavailable', () => {
    vi.unstubAllGlobals()
    expect(getApiBaseUrl()).toBe('')
  })

  it('uses a configured API URL without a trailing slash', () => {
    expect(getApiBaseUrl('https://api.fanoosai.example/')).toBe('https://api.fanoosai.example')
  })

  it('prefers a configured URL over window.location.origin', () => {
    vi.stubGlobal('window', { location: { origin: 'https://ignored.example' } })
    expect(getApiBaseUrl('https://api.example')).toBe('https://api.example')
  })
})
