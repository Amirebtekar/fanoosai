import type { CompetitorRadarBrand } from '@/lib/api'

export const RADAR_AXES = [
  { key: 'visibility', label: 'دیده‌شدن', hint: 'درصد پاسخ‌هایی که برند در آن‌ها آمده' },
  { key: 'rank_score', label: 'رتبه', hint: 'امتیاز میانگین رتبه؛ رتبهٔ ۱ = ۱۰۰ و رتبهٔ ۱۰ = ۰. برای برندهایی که در کمتر از ۵٪ پاسخ‌ها آمده‌اند به نسبت کم می‌شود' },
  { key: 'top_three', label: 'حضور در ۳ رتبه اول', hint: 'درصد حضورهای برند که رتبهٔ ۳ یا بهتر داشته‌اند؛ تعداد حضور در ۳ رتبه اول تقسیم بر کل حضورهای برند، بدون کاهش بابت حجم نمونه' },
  { key: 'model_coverage', label: 'پوشش مدل‌ها', hint: 'درصد مدل‌هایی که برند را آورده‌اند' },
  { key: 'prompt_coverage', label: 'پوشش پرامپت‌ها', hint: 'درصد پرامپت‌هایی که برند در آن‌ها آمده' },
] as const

export type RadarAxisKey = (typeof RADAR_AXES)[number]['key']

export function topThreeDetails(brand: CompetitorRadarBrand): string {
  return `حضور در ۳ رتبه اول: ${brand.top_three.toLocaleString('fa-IR')}٪ (${brand.top_three_count.toLocaleString('fa-IR')} از ${brand.appearances.toLocaleString('fa-IR')} حضور)`
}

export const OWN_BRAND_COLOR = '#f97316'
export const COMPETITOR_COLORS = ['#2563eb', '#16a34a', '#9333ea', '#0891b2', '#dc2626', '#ca8a04', '#db2777', '#4f46e5', '#65a30d']

/** Assign a stable colour per brand: own brand always orange, competitors in order. */
export function radarSeries(brands: CompetitorRadarBrand[]) {
  let competitorIndex = 0
  return brands.map(brand => ({
    ...brand,
    key: `brand_${brand.brand_id}`,
    color: brand.is_owned ? OWN_BRAND_COLOR : COMPETITOR_COLORS[competitorIndex++ % COMPETITOR_COLORS.length],
  }))
}

/** Recharts radar rows: one row per axis, one numeric column per brand. */
export function radarRows(series: ReturnType<typeof radarSeries>, visible: Set<string>) {
  return RADAR_AXES.map(axis => {
    const rowValues: Record<string, string | number> = { axis: axis.label }
    for (const item of series) if (visible.has(item.key)) rowValues[item.key] = item[axis.key]
    return rowValues
  })
}

/** Short Persian explanation of how a competitor compares with the own brand. */
export function compareWithOwn(brand: CompetitorRadarBrand, own: CompetitorRadarBrand | undefined): string {
  if (!own || brand.is_owned) return ''
  const diff = Math.round((brand.strength - own.strength) * 10) / 10
  if (Math.abs(diff) < 1) return 'هم‌تراز با شما'
  return diff > 0 ? `${diff.toLocaleString('fa-IR')} امتیاز قوی‌تر از شما` : `${Math.abs(diff).toLocaleString('fa-IR')} امتیاز ضعیف‌تر از شما`
}
