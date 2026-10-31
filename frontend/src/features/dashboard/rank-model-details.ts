import { addDays, format } from 'date-fns'
import type { BrandRankSummaryItem, BrandTrend, CompetitorRadarBrand } from '@/lib/api'
import { escapeHtml, radarSvg } from './competitor-radar-data'

export function tehranReportDays(days: 7 | 30, now = new Date()): string[] {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Tehran',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(now)
  const part = (type: Intl.DateTimeFormatPartTypes) => parts.find(item => item.type === type)?.value ?? ''
  const today = new Date(Number(part('year')), Number(part('month')) - 1, Number(part('day')))
  return Array.from({ length: days }, (_, index) => format(addDays(today, -index), 'yyyy-MM-dd'))
}

export function summarizeModelRanks(items: BrandTrend[], dayKeys: string[]) {
  const chronological = [...dayKeys].reverse()
  return items.map(item => {
    const daily: Record<string, number> = {}
    let observations = 0
    for (const point of [...item.points].sort((a, b) => a.date.localeCompare(b.date))) {
      const date = new Date(point.date)
      const parts = new Intl.DateTimeFormat('en-CA', {
        timeZone: 'Asia/Tehran',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
      }).formatToParts(date)
      const part = (type: Intl.DateTimeFormatPartTypes) => parts.find(value => value.type === type)?.value ?? ''
      const day = `${part('year')}-${part('month')}-${part('day')}`
      if (!dayKeys.includes(day)) continue
      daily[day] = point.rank
      observations += 1
    }
    const seenDays = chronological.filter(day => daily[day] !== undefined)
    const ranks = seenDays.map(day => daily[day])
    return {
      ai_model_id: item.ai_model_id,
      ai_model: item.ai_model,
      average_rank: ranks.length ? ranks.reduce((sum, rank) => sum + rank, 0) / ranks.length : null,
      latest_rank: seenDays.length ? daily[seenDays[seenDays.length - 1]] : null,
      rank_change: seenDays.length > 1 ? daily[seenDays[seenDays.length - 1]] - daily[seenDays[0]] : null,
      observations,
      daily,
    }
  }).sort((a, b) => (a.average_rank ?? Infinity) - (b.average_rank ?? Infinity) || a.ai_model.localeCompare(b.ai_model))
}

/** Total answers the brand could have appeared in (never below its observations). */
export function observationTotal(item: Pick<BrandRankSummaryItem, 'observations' | 'total_runs'>): number {
  return Math.max(item.total_runs ?? item.observations, item.observations)
}

/** "34 از 35" style label; falls back to the plain count when the total is unknown. */
export function observationLabel(item: Pick<BrandRankSummaryItem, 'observations' | 'total_runs'>, locale = 'fa-IR'): string {
  const seen = item.observations.toLocaleString(locale)
  if (item.total_runs == null) return seen
  return `${seen} از ${observationTotal(item).toLocaleString(locale)}`
}

export function brandRankSummaryCsv(items: BrandRankSummaryItem[]): string {
  const headers = ['پرامپت', 'برند', 'دامنه', 'میانگین رتبه', 'تعداد مشاهده', 'تعداد کل پاسخ‌ها']
  const values = items.map(item => [item.prompt, item.brand, item.domain ?? '', item.average_rank.toFixed(2), item.observations, observationTotal(item)])
  const escape = (value: string | number) => {
    const text = String(value)
    const safeText = /^\s*[=+\-@]/.test(text) ? `'${text}` : text
    return `"${safeText.replace(/"/g, '""')}"`
  }
  return `\uFEFF${[headers, ...values].map(line => line.map(escape).join(',')).join('\r\n')}`
}

function printTable(headers: string[], rows: (string | number)[][]): string {
  const head = headers.map(label => `<th>${escapeHtml(label)}</th>`).join('')
  const body = rows.map(row => `<tr>${row.map(cell => `<td>${escapeHtml(cell)}</td>`).join('')}</tr>`).join('')
  return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`
}

function radarPrintSection(brands: CompetitorRadarBrand[]): string {
  const svg = radarSvg(brands)
  if (!svg) return ''
  const table = printTable(
    ['برند', 'امتیاز قدرت', 'دیده‌شدن (٪)', 'میانگین رتبه', 'حضور در ۳ رتبه اول (٪)'],
    brands.map(brand => [`${brand.brand}${brand.is_owned ? ' (شما)' : ''}`, brand.strength, brand.visibility, brand.average_rank?.toFixed(2) ?? '—', `${brand.top_three} (${brand.top_three_count} از ${brand.appearances})`]),
  )
  return `<section class="page-section"><h2>رادار رقبا</h2><div class="radar">${svg}</div>${table}</section>`
}

export const PRINT_FONT_URL = 'https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700;800&amp;display=block'
export const PRINT_FONT_FAMILY = "'Vazirmatn',Tahoma,sans-serif"

export async function waitForPrintFonts(doc: Document, timeoutMs = 4000): Promise<void> {
  const fonts = (doc as Document & { fonts?: FontFaceSet }).fonts
  if (!fonts) return
  const loading = Promise.all([
    fonts.load("400 12px 'Vazirmatn'", 'آ'),
    fonts.load("700 12px 'Vazirmatn'", 'آ'),
  ]).then(() => fonts.ready).then(() => undefined, () => undefined)
  await Promise.race([loading, new Promise<void>(resolve => setTimeout(resolve, timeoutMs))])
}

export function brandRankSummaryPrintHtml(
  items: BrandRankSummaryItem[],
  filters: { project: string; prompt: string; brand: string; days: number },
  extras: { radar?: CompetitorRadarBrand[] | null } = {},
): string {
  const escape = escapeHtml
  const rows = items.map(item => `<tr><td>${escape(item.prompt)}</td><td>${escape(item.brand)}</td><td dir="ltr">${escape(item.domain ?? '—')}</td><td>${escape(item.average_rank.toFixed(2))}</td><td>${escape(observationLabel(item, 'en-US'))}</td></tr>`).join('')
  const sections = extras.radar ? radarPrintSection(extras.radar) : ''
  return `<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><title>گزارش رتبه برندها</title><link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link rel="stylesheet" href="${PRINT_FONT_URL}"><style>@page{size:landscape;margin:12mm}body{font-family:${PRINT_FONT_FAMILY};color:#111;margin:0}svg text{font-family:${PRINT_FONT_FAMILY}}h1{font-size:20px;margin:0 0 12px}h2{font-size:17px;margin:0 0 10px}h3{font-size:13px;margin:16px 0 8px}p{font-size:12px;margin:4px 0 16px}.filters{display:flex;gap:18px;flex-wrap:wrap;font-size:11px;margin-bottom:14px}table{width:100%;border-collapse:collapse;font-size:10px}th,td{border:1px solid #777;padding:6px;text-align:right}th{background:#eee}tbody tr{break-inside:avoid}.page-section{break-before:page;page-break-before:always}.radar{display:flex;justify-content:center;margin-bottom:14px}.radar svg{max-width:100%;height:auto;max-height:150mm;break-inside:avoid}</style></head><body><h1>گزارش رتبه برندها</h1><div class="filters"><span>پروژه: ${escape(filters.project)}</span><span>پرامپت: ${escape(filters.prompt)}</span><span>برند: ${escape(filters.brand)}</span><span>بازه: ${escape(filters.days)} روز</span></div><table><thead><tr>${['پرامپت','برند','دامنه','میانگین رتبه','تعداد مشاهده'].map(label => `<th>${label}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table>${sections}</body></html>`
}

export function tehranBounds(dayKeys: string[]) {
  const start = [...dayKeys].reverse()[0]
  const end = dayKeys[0]
  return {
    start_date: `${start}T00:00:00+03:30`,
    end_date: `${end}T23:59:59+03:30`,
  }
}
