import { describe, expect, it } from 'vitest'

import { brandRankSummaryCsv, brandRankSummaryPrintHtml, summarizeModelRanks, tehranBounds, tehranReportDays } from './rank-model-details'

describe('dashboard brand rank model details', () => {
  it('averages daily ranks by model over all models and includes all days', () => {
    const days = ['2026-09-27', '2026-09-26']
    const rows = summarizeModelRanks([
      {
        brand_id: 1,
        brand: 'پارس‌پک',
        domain: 'parspack.com',
        ai_model_id: 7,
        ai_model: 'model-a',
        points: [
          { date: '2026-09-25T22:00:00Z', rank: 2, ai_run_id: 1 },
          { date: '2026-09-26T22:00:00Z', rank: 4, ai_run_id: 2 },
        ],
        trend: 'down',
      },
      {
        brand_id: 1,
        brand: 'پارس‌پک',
        domain: 'parspack.com',
        ai_model_id: 8,
        ai_model: 'model-b',
        points: [{ date: '2026-09-26T22:00:00Z', rank: 1, ai_run_id: 3 }],
        trend: 'flat',
      },
    ], days)

    expect(rows[0]).toMatchObject({ ai_model: 'model-b', average_rank: 1, latest_rank: 1, rank_change: null, observations: 1 })
    expect(rows[1]).toMatchObject({ ai_model: 'model-a', average_rank: 3, latest_rank: 4, rank_change: 2, observations: 2 })
    expect(rows[1].daily).toEqual({ '2026-09-26': 2, '2026-09-27': 4 })
  })

  it('exports all filtered summary rows and prevents spreadsheet formulas', () => {
    const csv = brandRankSummaryCsv([
      { prompt_id: 1, prompt: 'هاست "ارزان"', brand_id: 2, brand: 'پارس‌پک', domain: 'parspack.com', average_rank: 2.5, observations: 3 },
      { prompt_id: 3, prompt: '=HYPERLINK("https://bad.example")', brand_id: 4, brand: 'ایران‌سرور', domain: null, average_rank: 1, observations: 1 },
    ])

    expect(csv.charCodeAt(0)).toBe(0xFEFF)
    expect(csv).toContain('"هاست ""ارزان""","پارس‌پک","parspack.com","2.50","3"')
    expect(csv).toContain('"\'=HYPERLINK(""https://bad.example"")","ایران‌سرور","","1.00","1"')
    expect(csv.split('\r\n')).toHaveLength(3)
  })

  it('prints the whole filtered summary and escapes user-provided text', () => {
    const html = brandRankSummaryPrintHtml([
      { prompt_id: 1, prompt: '<script>alert(1)</script>', brand_id: 2, brand: 'پارس‌پک', domain: 'parspack.com', average_rank: 2.5, observations: 3 },
    ], { project: '<img src=x>', prompt: 'همه', brand: 'پارس‌پک', days: 7 })

    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;')
    expect(html).toContain('&lt;img src=x&gt;')
    expect(html).toContain('2.50')
    expect(html).not.toContain('<script>alert(1)</script>')
  })

  it('builds a seven-day Tehran range and UTC query boundaries', () => {
    const now = new Date('2026-09-28T08:00:00Z')
    const days = tehranReportDays(7, now)

    expect(days).toHaveLength(7)
    expect(days[0]).toBe('2026-09-28')
    expect(days[6]).toBe('2026-09-22')
    expect(tehranBounds(days)).toEqual({
      start_date: '2026-09-22T00:00:00+03:30',
      end_date: '2026-09-28T23:59:59+03:30',
    })
  })
})
