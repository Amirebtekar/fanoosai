import { addDays, format } from 'date-fns'
import type { BrandRankSummaryItem, BrandTrend } from '@/lib/api'

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

export function brandRankSummaryCsv(items: BrandRankSummaryItem[]): string {
  const headers = ['پرامپت', 'برند', 'دامنه', 'میانگین رتبه', 'تعداد مشاهده']
  const values = items.map(item => [item.prompt, item.brand, item.domain ?? '', item.average_rank.toFixed(2), item.observations])
  const escape = (value: string | number) => {
    const text = String(value)
    const safeText = /^\s*[=+\-@]/.test(text) ? `'${text}` : text
    return `"${safeText.replace(/"/g, '""')}"`
  }
  return `\uFEFF${[headers, ...values].map(line => line.map(escape).join(',')).join('\r\n')}`
}

export function brandRankSummaryPrintHtml(
  items: BrandRankSummaryItem[],
  filters: { project: string; prompt: string; brand: string; days: number }
): string {
  const escape = (value: string | number) => String(value).replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character] ?? character)
  const rows = items.map(item => `<tr><td>${escape(item.prompt)}</td><td>${escape(item.brand)}</td><td dir="ltr">${escape(item.domain ?? '—')}</td><td>${escape(item.average_rank.toFixed(2))}</td><td>${escape(item.observations)}</td></tr>`).join('')
  return `<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><title>گزارش رتبه برندها</title><style>@page{size:landscape;margin:12mm}body{font-family:Arial,sans-serif;color:#111;margin:0}h1{font-size:20px;margin:0 0 12px}p{font-size:12px;margin:4px 0 16px}.filters{display:flex;gap:18px;flex-wrap:wrap;font-size:11px;margin-bottom:14px}table{width:100%;border-collapse:collapse;font-size:10px}th,td{border:1px solid #777;padding:6px;text-align:right}th{background:#eee}tbody tr{break-inside:avoid}</style></head><body><h1>گزارش رتبه برندها</h1><div class="filters"><span>پروژه: ${escape(filters.project)}</span><span>پرامپت: ${escape(filters.prompt)}</span><span>برند: ${escape(filters.brand)}</span><span>بازه: ${escape(filters.days)} روز</span></div><table><thead><tr>${['پرامپت','برند','دامنه','میانگین رتبه','تعداد مشاهده'].map(label => `<th>${label}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table></body></html>`
}

export function tehranBounds(dayKeys: string[]) {
  const start = [...dayKeys].reverse()[0]
  const end = dayKeys[0]
  return {
    start_date: `${start}T00:00:00+03:30`,
    end_date: `${end}T23:59:59+03:30`,
  }
}
