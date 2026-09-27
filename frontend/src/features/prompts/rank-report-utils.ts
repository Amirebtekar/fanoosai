import { addDays, differenceInCalendarDays, format } from 'date-fns'
import type { BrandTrend } from '@/lib/api'

export function tehranDateKey(value: string | Date): string {
  const date = value instanceof Date ? value : new Date(value)
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Tehran',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date)
  const part = (type: Intl.DateTimeFormatPartTypes) => parts.find(item => item.type === type)?.value ?? ''
  return `${part('year')}-${part('month')}-${part('day')}`
}

export function rankReportDays(startDate: Date, endDate: Date): string[] {
  const count = differenceInCalendarDays(endDate, startDate)
  return Array.from({ length: count + 1 }, (_, index) => format(addDays(startDate, index), 'yyyy-MM-dd')).reverse()
}

export function buildRankTableRows(
  items: BrandTrend[],
  days: string[],
  today: string,
  yesterday: string,
  modelFilter = 'all',
  brandFilter = 'all',
  search = ''
) {
  const firstDay = [...days].reverse()
  const query = search.trim().toLocaleLowerCase()
  return items.flatMap(item => {
    if (modelFilter !== 'all' && String(item.ai_model_id) !== modelFilter) return []
    if (brandFilter !== 'all' && String(item.brand_id) !== brandFilter) return []
    if (query && !`${item.brand} ${item.domain ?? ''} ${item.ai_model}`.toLocaleLowerCase().includes(query)) return []
    const daily: Record<string, number> = {}
    for (const point of [...item.points].sort((a, b) => a.date.localeCompare(b.date))) {
      const day = tehranDateKey(point.date)
      if (days.includes(day)) daily[day] = point.rank
    }
    const observedDays = firstDay.filter(day => daily[day] !== undefined)
    if (!observedDays.length) return []
    const ranks = observedDays.map(day => daily[day])
    return [{
      ...item,
      daily,
      average: ranks.reduce((sum, rank) => sum + rank, 0) / ranks.length,
      change: observedDays.length > 1 ? daily[observedDays[observedDays.length - 1]] - daily[observedDays[0]] : null,
      today: daily[today] ?? null,
      yesterday: daily[yesterday] ?? null,
    }]
  }).sort((a, b) => (a.average ?? Infinity) - (b.average ?? Infinity) || a.brand.localeCompare(b.brand))
}
