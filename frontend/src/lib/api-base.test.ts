import { describe, expect, it } from 'vitest'
import { getApiBaseUrl } from './api-base'

describe('getApiBaseUrl', () => {
  it('uses the local API as a development fallback', () => {
    expect(getApiBaseUrl()).toBe('http://localhost:8000')
  })

  it('uses a configured API URL without a trailing slash', () => {
    expect(getApiBaseUrl('https://api.fanoosai.example/')).toBe('https://api.fanoosai.example')
  })
})
