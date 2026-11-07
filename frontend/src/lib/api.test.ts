import { describe, expect, it, vi } from 'vitest'
import { adminSearchQueriesExportUrl, ApiError, getAllBrandRankSummary, getCompetitorRadar, getErrorMessage, getPromptBrandTrends, getProjectSearchedSites, getProjectSearchQueries, listAdminSearchQueries } from './api'

describe('search query endpoints', () => {
  it('builds project and admin URLs with only the given filters', async () => {
    const originalFetch = globalThis.fetch
    const requestedUrls: string[] = []
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      requestedUrls.push(String(input))
      return { ok: true, status: 200, text: async () => JSON.stringify({ items: [], page: 1, page_size: 50, total: 0 }) } as Response
    }) as typeof fetch
    try {
      await getProjectSearchQueries(10, { prompt_id: 33, page: 2 })
      await getProjectSearchedSites(10, { prompt_id: 33, ai_model_id: undefined })
      await listAdminSearchQueries({ search: '', page: 1, page_size: 50 })
      await listAdminSearchQueries({ search: 'vps هاست', project_id: 4 })
      expect(requestedUrls[0]).toMatch(/\/projects\/10\/search-queries\?prompt_id=33&page=2$/)
      expect(requestedUrls[1]).toMatch(/\/projects\/10\/searched-sites\?prompt_id=33$/)
      expect(requestedUrls[2]).toMatch(/\/admin\/search-queries\?page=1&page_size=50$/)
      expect(new URL(requestedUrls[3], 'http://test.local').searchParams.get('search')).toBe('vps هاست')
      expect(adminSearchQueriesExportUrl()).toMatch(/\/admin\/search-queries\/export$/)
      expect(adminSearchQueriesExportUrl({ search: 'a b' })).toMatch(/\/admin\/search-queries\/export\?search=a\+b$/)
    } finally {
      globalThis.fetch = originalFetch
    }
  })
})

describe('getAllBrandRankSummary', () => {
  it('loads every page using the selected project, prompt, brand and period filters', async () => {
    const originalFetch = globalThis.fetch
    const requestedUrls: string[] = []
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      requestedUrls.push(url)
      const page = Number(new URL(url, 'http://test.local').searchParams.get('page'))
      const items = Array.from({ length: page === 1 ? 100 : 1 }, (_, index) => ({
        prompt_id: 33,
        prompt: 'prompt text',
        brand_id: 2,
        brand: `Brand ${index}`,
        domain: 'brand.example',
        average_rank: 1.5,
        observations: 1,
      }))
      return { ok: true, status: 200, text: async () => JSON.stringify({ items, page, page_size: 100, total: 101 }) } as Response
    })
    globalThis.fetch = fetchMock as typeof fetch
    try {
      const items = await getAllBrandRankSummary(10, { days: 7, prompt_id: 33, brand_id: 2 })
      expect(items).toHaveLength(101)
      expect(requestedUrls).toHaveLength(2)
      expect(requestedUrls[0]).toContain('/projects/10/brand-rank-summary?')
      expect(requestedUrls[0]).toContain('prompt_id=33')
      expect(requestedUrls[0]).toContain('brand_id=2')
      expect(requestedUrls[0]).toContain('days=7')
      expect(requestedUrls[1]).toContain('page=2')
    } finally {
      globalThis.fetch = originalFetch
    }
  })
})

describe('model filter', () => {
  const stubFetch = (body: unknown) => {
    const originalFetch = globalThis.fetch
    const requestedUrls: string[] = []
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      requestedUrls.push(String(input))
      return { ok: true, status: 200, text: async () => JSON.stringify(body) } as Response
    }) as typeof fetch
    return { requestedUrls, restore: () => { globalThis.fetch = originalFetch } }
  }

  it('sends ai_model_id for the brand rank summary and omits it when unset', async () => {
    const { requestedUrls, restore } = stubFetch({ items: [], page: 1, page_size: 100, total: 0 })
    try {
      await getAllBrandRankSummary(10, { days: 30, prompt_id: 33, brand_id: 2, ai_model_id: 5 })
      await getAllBrandRankSummary(10, { days: 7, ai_model_id: undefined })
      expect(requestedUrls[0]).toMatch(/\/projects\/10\/brand-rank-summary\?days=30&prompt_id=33&brand_id=2&ai_model_id=5&page=1&page_size=100$/)
      expect(requestedUrls[1]).not.toContain('ai_model_id')
    } finally {
      restore()
    }
  })

  it('sends ai_model_id for the competitor radar and trends', async () => {
    const { requestedUrls, restore } = stubFetch({ days: 7, total_runs: 0, total_models: 0, total_prompts: 0, brands: [], prompt_id: 1, items: [] })
    try {
      await getCompetitorRadar(10, { days: 7, prompt_id: 33, ai_model_id: 5, limit: 6 })
      await getCompetitorRadar(10, { days: 7, limit: 6 })
      await getPromptBrandTrends(33, { brand_ids: [2], ai_model_id: 5 })
      expect(requestedUrls[0]).toMatch(/\/projects\/10\/competitor-radar\?days=7&prompt_id=33&ai_model_id=5&limit=6$/)
      expect(requestedUrls[1]).not.toContain('ai_model_id')
      expect(requestedUrls[2]).toContain('ai_model_id=5')
      expect(requestedUrls[2]).toContain('brand_ids=2')
    } finally {
      restore()
    }
  })

  it('accepts rows with a null average rank', async () => {
    const row = { prompt_id: 1, prompt: 'p', brand_id: 2, brand: 'b', domain: null, average_rank: null, observations: 0, total_runs: 12 }
    const { restore } = stubFetch({ items: [row], page: 1, page_size: 100, total: 1 })
    try {
      const items = await getAllBrandRankSummary(10, { days: 7, brand_id: 2 })
      expect(items).toEqual([row])
    } finally {
      restore()
    }
  })
})

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
