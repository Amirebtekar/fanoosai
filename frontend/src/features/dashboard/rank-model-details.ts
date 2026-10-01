import { addDays, format } from 'date-fns'
import type { BrandTrend } from '@/lib/api'

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

export function rankDetailsCsv(rows: ReturnType<typeof summarizeModelRanks>, dayKeys: string[]): string {
  const headers = ['مدل', 'میانگین رتبه', 'آخرین رتبه', 'تغییر', 'تعداد مشاهده', ...dayKeys]
  const values = rows.map(row => [
    row.ai_model,
    row.average_rank?.toFixed(2) ?? '',
    row.latest_rank ?? '',
    row.rank_change ?? '',
    row.observations,
    ...dayKeys.map(day => row.daily[day] ?? ''),
  ])
  const escape = (value: string | number) => `"${String(value).replace(/"/g, '""')}"`
  return `\uFEFF${[headers, ...values].map(line => line.map(escape).join(',')).join('\r\n')}`
}

export function tehranBounds(dayKeys: string[]) {
  const start = [...dayKeys].reverse()[0]
  const end = dayKeys[0]
  return {
    start_date: `${start}T00:00:00+03:30`,
    end_date: `${end}T23:59:59+03:30`,
  }
}
