import { describe, expect, it } from 'vitest'

import { PRINT_FONT_URL, brandRankSummaryCsv, brandRankSummaryPrintHtml, observationLabel, observationTotal, summarizeModelRanks, tehranBounds, tehranReportDays, waitForPrintFonts } from './rank-model-details'

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

  it('exports all filtered summary rows and prevents spreadsheet formulas', () => {
    const csv = brandRankSummaryCsv([
      { prompt_id: 1, prompt: 'هاست "ارزان"', brand_id: 2, brand: 'پارس‌پک', domain: 'parspack.com', average_rank: 2.5, observations: 3, total_runs: 4 },
      { prompt_id: 3, prompt: '=HYPERLINK("https://bad.example")', brand_id: 4, brand: 'ایران‌سرور', domain: null, average_rank: 1, observations: 1 },
    ])

    expect(csv.charCodeAt(0)).toBe(0xFEFF)
    expect(csv).toContain('"تعداد مشاهده","تعداد کل پاسخ‌ها"')
    expect(csv).toContain('"هاست ""ارزان""","پارس‌پک","parspack.com","2.50","3","4"')
    expect(csv).toContain('"\'=HYPERLINK(""https://bad.example"")","ایران‌سرور","","1.00","1","1"')
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

  it('appends the radar and prompt leadership after the summary, escaped', () => {
    const radar = [
      { brand_id: 1, brand: '<b>arvan</b>', domain: null, is_owned: false, strength: 80, visibility: 90, rank_score: 90, top_three: 95, model_coverage: 100, prompt_coverage: 100, appearances: 30, average_rank: 1.1, top_three_count: 28, models: 5, prompts: 1 },
      { brand_id: 2, brand: 'پارس‌پک', domain: 'parspack.com', is_owned: true, strength: 50, visibility: 70, rank_score: 60, top_three: 40, model_coverage: 80, prompt_coverage: 100, appearances: 25, average_rank: 3.2, top_three_count: 10, models: 4, prompts: 1 },
    ]
    const leader = { brand_id: 1, brand: '<b>arvan</b>', domain: null, average_rank: 1.1, appearances: 30 }
    const leaders = {
      days: 7,
      has_own_brand: true,
      items: [
        { prompt_id: 29, prompt: 'CDN <i>x</i>', total_runs: 32, leader, own: { brand_id: 2, brand: 'پارس‌پک', domain: 'parspack.com', average_rank: 3.2, appearances: 25, position: 3, eligible: true }, own_is_leader: false },
        { prompt_id: 30, prompt: 'hosting', total_runs: 10, leader, own: null, own_is_leader: false },
        { prompt_id: 31, prompt: 'vps', total_runs: 20, leader: { ...leader, brand_id: 2, brand: 'پارس‌پک' }, own: { brand_id: 2, brand: 'پارس‌پک', domain: null, average_rank: 1.5, appearances: 18, position: 1, eligible: true }, own_is_leader: true },
      ],
    }
    const html = brandRankSummaryPrintHtml([
      { prompt_id: 1, prompt: 'p', brand_id: 2, brand: 'b', domain: null, average_rank: 1, observations: 3 },
    ], { project: 'x', prompt: 'y', brand: 'z', days: 7 }, { radar, leaders })

    expect(html.indexOf('</table>')).toBeLessThan(html.indexOf('<svg'))
    expect(html.match(/<polygon data-brand=/g)).toHaveLength(2)
    expect(html).toContain('page-break-before:always')
    expect(html).not.toContain('<b>arvan</b>')
    expect(html).not.toContain('<i>x</i>')
    expect(html).toContain('&lt;b&gt;arvan&lt;/b&gt;')
    expect(html).toContain('<td>CDN &lt;i&gt;x&lt;/i&gt;</td><td>&lt;b&gt;arvan&lt;/b&gt;</td><td>1.10</td><td>رتبه 3 از برندهای پرتکرار</td><td>3.20</td>')
    expect(html).toContain('<td>hosting</td><td>&lt;b&gt;arvan&lt;/b&gt;</td><td>1.10</td><td>در پاسخ‌ها دیده نشده‌اید</td><td>—</td>')
    expect(html).toContain('<td>vps</td><td>1.50</td><td>18 از 20 پاسخ</td>')
    expect(html).toContain('اول نیستید (2)')
    expect(html).toContain('اول هستید (1)')
    expect(html).toContain('<td>پارس‌پک (شما)</td><td>50</td><td>70</td><td>3.20</td><td>40 (10 از 25)</td>')
  })

  it('omits optional sections when data is missing or empty', () => {
    const html = brandRankSummaryPrintHtml([], { project: 'x', prompt: 'y', brand: 'z', days: 30 }, { radar: [], leaders: null })
    expect(html).not.toContain('<svg')
    expect(html).not.toContain('page-section"')
    const hint = brandRankSummaryPrintHtml([], { project: 'x', prompt: 'y', brand: 'z', days: 30 }, { leaders: { days: 30, has_own_brand: false, items: [] } })
    expect(hint).toContain('برند خود را در تنظیمات پروژه تعریف کنید.')
    expect(hint).not.toContain('<svg')
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
