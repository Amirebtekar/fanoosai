import { describe, expect, it } from 'vitest'

import { NOT_SEEN_LABEL, PRINT_FONT_URL, brandRankSummaryCsv, brandRankSummaryPrintHtml, effectiveRankCoefficient, isNotSeen, observationLabel, observationTotal, projectModelOptions, summarizeModelCoverage, summarizeModelRanks, tehranBounds, tehranReportDays, waitForPrintFonts } from './rank-model-details'

describe('print font', () => {
  it('loads Vazirmatn and uses it for body and chart text', () => {
    const html = brandRankSummaryPrintHtml([], { project: 'p', prompt: 'q', brand: 'b', days: 7 })
    expect(html).toContain(`<link rel="stylesheet" href="${PRINT_FONT_URL}">`)
    expect(PRINT_FONT_URL).toContain('family=Vazirmatn')
    expect(html).toContain("body{font-family:'Vazirmatn',Tahoma,sans-serif")
    expect(html).toContain("svg text{font-family:'Vazirmatn',Tahoma,sans-serif}")
    expect(html).not.toContain('Arial')
  })

  it('waits for the font but never blocks printing', async () => {
    const loads: string[] = []
    const ready = { load: (font: string) => { loads.push(font); return Promise.resolve([]) }, ready: Promise.resolve() }
    await waitForPrintFonts({ fonts: ready } as unknown as Document)
    expect(loads).toHaveLength(2)

    const stuck = { load: () => new Promise(() => {}), ready: new Promise(() => {}) }
    const started = Date.now()
    await waitForPrintFonts({ fonts: stuck } as unknown as Document, 50)
    expect(Date.now() - started).toBeLessThan(1000)

    await waitForPrintFonts({} as Document)
  })
})

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

  it('includes models with no observations and retains incomplete extraction coverage', () => {
    const rows = summarizeModelCoverage([
      { ai_model_id: 1, ai_model: 'Luna', successful_runs: 7, completed_extractions: 7, incomplete_extractions: 0, points: [] },
      { ai_model_id: 2, ai_model: 'unknown', successful_runs: 2, completed_extractions: 0, incomplete_extractions: 2, points: [] },
      { ai_model_id: 3, ai_model: 'seen', successful_runs: 2, completed_extractions: 2, incomplete_extractions: 0, points: [
        { date: '2026-09-26T22:00:00Z', rank: 1, ai_run_id: 1 },
        { date: '2026-09-26T23:00:00Z', rank: 2, ai_run_id: 2 },
      ] },
    ], ['2026-09-27'])
    expect(rows.find(row => row.ai_model === 'Luna')).toMatchObject({ observations: 0, average_rank: null, latest_rank: null, rank_change: null, successful_runs: 7, daily: {} })
    expect(rows.find(row => row.ai_model === 'unknown')).toMatchObject({ observations: 0, incomplete_extractions: 2 })
    expect(rows.find(row => row.ai_model === 'seen')).toMatchObject({ observations: 2 })
  })

  it('exports all filtered summary rows and prevents spreadsheet formulas', () => {
    const csv = brandRankSummaryCsv([
      { prompt_id: 1, prompt: 'هاست "ارزان"', brand_id: 2, brand: 'پارس‌پک', domain: 'parspack.com', average_rank: 2.5, observations: 3, total_runs: 4 },
      { prompt_id: 3, prompt: '=HYPERLINK("https://bad.example")', brand_id: 4, brand: 'ایران‌سرور', domain: null, average_rank: 1, observations: 1 },
      { prompt_id: 5, prompt: 'دیده‌نشده', brand_id: 6, brand: 'آروان', domain: null, average_rank: null, observations: 0 },
    ])

    expect(csv.charCodeAt(0)).toBe(0xFEFF)
    expect(csv).toContain('"تعداد مشاهده","تعداد کل پاسخ‌ها","ضریب رتبه موثر"')
    // (1 / 3/4) × 2.5 ≈ 3.33
    expect(csv).toContain('"هاست ""ارزان""","پارس‌پک","parspack.com","2.50","3","4","3.33"')
    expect(csv).toContain('"\'=HYPERLINK(""https://bad.example"")","ایران‌سرور","","1.00","1","1","1.00"')
    expect(csv).toContain('"دیده‌نشده","آروان","","","0","0",""')
    expect(csv.split('\r\n')).toHaveLength(4)
  })

  it('prints the whole filtered summary and escapes user-provided text', () => {
    const html = brandRankSummaryPrintHtml([
      { prompt_id: 1, prompt: '<script>alert(1)</script>', brand_id: 2, brand: 'پارس‌پک', domain: 'parspack.com', average_rank: 2.5, observations: 3 },
    ], { project: '<img src=x>', prompt: 'همه', brand: 'پارس‌پک', days: 7 })

    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;')
    expect(html).toContain('&lt;img src=x&gt;')
    expect(html).toContain('ضریب رتبه موثر')
    expect(html).toContain('<td>2.50</td><td>3</td><td>2.50</td>')
    expect(html).not.toContain('<script>alert(1)</script>')
  })

  it('appends the radar after the summary, escaped, without the prompt leadership section', () => {
    const radar = [
      { brand_id: 1, brand: '<b>arvan</b>', domain: null, is_owned: false, strength: 80, visibility: 90, rank_score: 90, top_three: 95, model_coverage: 100, prompt_coverage: 100, appearances: 30, average_rank: 1.1, top_three_count: 28, models: 5, prompts: 1 },
      { brand_id: 2, brand: 'پارس‌پک', domain: 'parspack.com', is_owned: true, strength: 50, visibility: 70, rank_score: 60, top_three: 40, model_coverage: 80, prompt_coverage: 100, appearances: 25, average_rank: 3.2, top_three_count: 10, models: 4, prompts: 1 },
    ]
    const html = brandRankSummaryPrintHtml([
      { prompt_id: 1, prompt: 'p', brand_id: 2, brand: 'b', domain: null, average_rank: 1, observations: 3 },
    ], { project: 'x', prompt: 'y', brand: 'z', days: 7 }, { radar })

    expect(html.indexOf('</table>')).toBeLessThan(html.indexOf('<svg'))
    expect(html.match(/<polygon data-brand=/g)).toHaveLength(2)
    expect(html).toContain('page-break-before:always')
    expect(html).not.toContain('<b>arvan</b>')
    expect(html).toContain('&lt;b&gt;arvan&lt;/b&gt;')
    expect(html).toContain('<td>پارس‌پک (شما)</td><td>50</td><td>70</td><td>3.20</td><td>40 (10 از 25)</td>')
    expect(html).not.toContain('جایگاه برند شما در پرامپت‌ها')
    expect(html).not.toContain('اول نیستید')
    expect(html).not.toContain('اول هستید')
  })

  it('omits the radar section when data is missing or empty', () => {
    for (const extras of [{ radar: [] }, { radar: null }, {}]) {
      const html = brandRankSummaryPrintHtml([], { project: 'x', prompt: 'y', brand: 'z', days: 30 }, extras)
      expect(html).not.toContain('<svg')
      expect(html).not.toContain('page-section"')
    }
  })

  it('computes the effective rank coefficient as rank divided by the view share', () => {
    // (1 / '34 از 35') * 1.5 ≈ 1.54 — a high share barely moves the rank
    expect(effectiveRankCoefficient({ average_rank: 1.5, observations: 34, total_runs: 35 })).toBe(1.54)
    // (1 / 50%) * 3 = 6 — half the answers doubles the rank
    expect(effectiveRankCoefficient({ average_rank: 3, observations: 5, total_runs: 10 })).toBe(6)
    // without a known total the share is full, so the rank stands on its own
    expect(effectiveRankCoefficient({ average_rank: 2.4, observations: 6 })).toBe(2.4)
    // no observation at all leaves the coefficient undefined
    expect(effectiveRankCoefficient({ average_rank: 1.8, observations: 0 })).toBeNull()
  })

  it('labels observations against the total number of answers', () => {
    expect(observationLabel({ observations: 34, total_runs: 35 })).toBe('۳۴ از ۳۵')
    expect(observationLabel({ observations: 34, total_runs: 35 }, 'en-US')).toBe('34 از 35')
    expect(observationLabel({ observations: 5 })).toBe('۵')
    expect(observationTotal({ observations: 6, total_runs: 4 })).toBe(6)

    const html = brandRankSummaryPrintHtml([
      { prompt_id: 1, prompt: 'p', brand_id: 2, brand: 'b', domain: null, average_rank: 1, observations: 34, total_runs: 35 },
    ], { project: 'x', prompt: 'y', brand: 'z', days: 7 })
    expect(html).toContain('<td>34 از 35</td>')
  })

  it('exports unseen brands with an empty average rank', () => {
    const csv = brandRankSummaryCsv([
      { prompt_id: 1, prompt: 'p', brand_id: 2, brand: 'b', domain: 'b.com', average_rank: null, observations: 0, total_runs: 32 },
    ])
    expect(csv).toContain('"p","b","b.com","","0","32"')
    expect(csv).not.toContain('null')
    expect(csv).not.toContain('NaN')
  })

  it('prints unseen brands with a dash and the not-seen label', () => {
    const html = brandRankSummaryPrintHtml([
      { prompt_id: 1, prompt: 'p', brand_id: 2, brand: 'b', domain: null, average_rank: null, observations: 0, total_runs: 32 },
      { prompt_id: 2, prompt: 'q', brand_id: 2, brand: 'b', domain: null, average_rank: 2, observations: 3, total_runs: 5 },
    ], { project: 'x', prompt: 'y', brand: 'z', days: 7 })
    expect(html).toContain(`<td>—</td><td>0 از 32 (${NOT_SEEN_LABEL})</td>`)
    expect(html).toContain('<td>2.00</td><td>3 از 5</td>')
    expect(html).not.toContain('null')
  })

  it('flags only rows without observations as not seen', () => {
    expect(isNotSeen({ observations: 0, average_rank: null })).toBe(true)
    expect(isNotSeen({ observations: 2, average_rank: 1.5 })).toBe(false)
    expect(observationLabel({ observations: 0, total_runs: 32 })).toBe('۰ از ۳۲')
  })

  it('lists the model filter in the print header only when given', () => {
    const item = { prompt_id: 1, prompt: 'p', brand_id: 2, brand: 'b', domain: null, average_rank: 1, observations: 1 }
    expect(brandRankSummaryPrintHtml([item], { project: 'x', prompt: 'y', brand: 'z', days: 7, model: '<GPT>' })).toContain('<span>مدل: &lt;GPT&gt;</span>')
    expect(brandRankSummaryPrintHtml([item], { project: 'x', prompt: 'y', brand: 'z', days: 7 })).not.toContain('مدل:')
  })

  it('derives unique model options sorted by name', () => {
    const model = (id: number, name: string) => ({ id, name, provider: 'p', model_key: String(id), is_active: true })
    expect(projectModelOptions([
      { models: [model(2, 'Gemini'), model(1, 'Claude')] },
      { models: [model(2, 'Gemini'), model(3, 'GPT')] },
      { models: [] },
    ])).toEqual([{ id: 1, name: 'Claude' }, { id: 2, name: 'Gemini' }, { id: 3, name: 'GPT' }])
    expect(projectModelOptions([])).toEqual([])
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
