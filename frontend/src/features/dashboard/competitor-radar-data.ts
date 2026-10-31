import type { CompetitorRadarBrand } from '@/lib/api'

export const RADAR_AXES = [
  { key: 'visibility', label: 'دیده‌شدن', hint: 'از همهٔ پاسخ‌های مدل‌ها در این بازه، برند در چند درصدشان آمده است. مثال: اگر ۳۵ پاسخ ثبت شده و برند در ۲۸ تایشان باشد، دیده‌شدن ۸۰٪ است. فرقش با «پوشش مدل‌ها» این است که اینجا تک‌تک پاسخ‌ها شمرده می‌شوند، نه تعداد مدل‌ها.' },
  { key: 'rank_score', label: 'رتبه', hint: 'امتیاز میانگین رتبه؛ رتبهٔ ۱ = ۱۰۰ و رتبهٔ ۱۰ = ۰. برای برندهایی که در کمتر از ۵٪ پاسخ‌ها آمده‌اند به نسبت کم می‌شود' },
  { key: 'top_three', label: 'حضور در ۳ رتبه اول', hint: 'درصد حضورهای برند که رتبهٔ ۳ یا بهتر داشته‌اند؛ تعداد حضور در ۳ رتبه اول تقسیم بر کل حضورهای برند، بدون کاهش بابت حجم نمونه' },
  { key: 'model_coverage', label: 'پوشش مدل‌ها', hint: 'از مدل‌های هوش مصنوعی که در این بازه پاسخ داده‌اند (مثل GPT، Claude، Gemini، Grok)، چند درصدشان دست‌کم یک بار اسم این برند را آورده‌اند؛ مهم نیست چند بار. مثال: اگر ۵ مدل فعال باشند و فقط GPT و Claude برند را نام برده باشند، پوشش مدل‌ها ۴۰٪ است. عدد پایین یعنی بعضی مدل‌ها اصلاً این برند را نمی‌شناسند یا پیشنهاد نمی‌دهند.' },
  { key: 'prompt_coverage', label: 'پوشش پرامپت‌ها', hint: 'از پرامپت‌هایی که در این بازه اجرا شده‌اند، برند در چند درصدشان دست‌کم یک بار آمده است. مثال: اگر ۱۰ پرامپت داشته باشید و برند فقط در پاسخ‌های ۶ پرامپت دیده شود، پوشش پرامپت‌ها ۶۰٪ است. عدد پایین یعنی برند فقط در موضوع‌های محدودی مطرح می‌شود.' },
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

export function escapeHtml(value: string | number): string {
  return String(value).replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character] ?? character)
}

export const RADAR_SVG = { centerX: 260, centerY: 210, radius: 150 } as const

/** Point of an axis value (0..100); axis 0 points straight up, then clockwise. */
export function radarPoint(axisIndex: number, value: number, axisCount = RADAR_AXES.length) {
  const angle = -Math.PI / 2 + (2 * Math.PI * axisIndex) / axisCount
  const distance = (value / 100) * RADAR_SVG.radius
  return {
    x: Math.round((RADAR_SVG.centerX + distance * Math.cos(angle)) * 10) / 10,
    y: Math.round((RADAR_SVG.centerY + distance * Math.sin(angle)) * 10) / 10,
  }
}

/** Static radar chart for printing; mirrors the on-screen colours. */
export function radarSvg(brands: CompetitorRadarBrand[]): string {
  if (!brands.length) return ''
  const series = radarSeries(brands)
  const { centerX, centerY, radius } = RADAR_SVG
  const points = (value: (index: number) => number) => RADAR_AXES.map((_, index) => {
    const point = radarPoint(index, value(index))
    return `${point.x},${point.y}`
  }).join(' ')
  const grid = [25, 50, 75, 100].map(level => `<polygon points="${points(() => level)}" fill="none" stroke="#ccc" stroke-width="1"/><text x="${centerX + 3}" y="${radarPoint(0, level).y - 2}" font-size="9" fill="#888" direction="ltr">${level}</text>`).join('')
  const spokes = RADAR_AXES.map((_, index) => {
    const end = radarPoint(index, 100)
    return `<line x1="${centerX}" y1="${centerY}" x2="${end.x}" y2="${end.y}" stroke="#ccc" stroke-width="1"/>`
  }).join('')
  const labels = RADAR_AXES.map((axis, index) => {
    const point = radarPoint(index, 112)
    const anchor = Math.abs(point.x - centerX) < 1 ? 'middle' : point.x > centerX ? 'end' : 'start'
    const dy = point.y < centerY - radius / 2 ? -4 : point.y > centerY + radius / 2 ? 12 : 4
    return `<text x="${point.x}" y="${point.y + dy}" text-anchor="${anchor}" direction="rtl" font-size="12" font-weight="700" fill="#111">${escapeHtml(axis.label)}</text>`
  }).join('')
  const ordered = [...series.filter(item => !item.is_owned), ...series.filter(item => item.is_owned)]
  const polygons = ordered.map(item => `<polygon data-brand="${escapeHtml(item.brand_id)}" points="${points(index => Math.max(0, Math.min(100, Number(item[RADAR_AXES[index].key]) || 0)))}" fill="${item.color}" fill-opacity="${item.is_owned ? 0.28 : 0.08}" stroke="${item.color}" stroke-width="${item.is_owned ? 3 : 2}"/>`).join('')
  const legendTop = centerY + radius + 50
  const legend = series.map((item, index) => {
    const y = legendTop + index * 20
    return `<rect x="494" y="${y - 10}" width="12" height="12" rx="2" fill="${item.color}"/><text x="486" y="${y}" text-anchor="start" direction="rtl" font-size="12" font-weight="${item.is_owned ? 700 : 400}" fill="#111">${escapeHtml(item.brand)}${item.is_owned ? ' (شما)' : ''} — قدرت ${escapeHtml(item.strength)}</text>`
  }).join('')
  const height = legendTop + series.length * 20
  return `<svg xmlns="http://www.w3.org/2000/svg" class="radar-chart" viewBox="0 0 520 ${height}" width="520" height="${height}" font-family="inherit" role="img" aria-label="نمودار راداری رقبا">${grid}${spokes}${polygons}${labels}${legend}</svg>`
}

/** Short Persian explanation of how a competitor compares with the own brand. */
export function compareWithOwn(brand: CompetitorRadarBrand, own: CompetitorRadarBrand | undefined): string {
  if (!own || brand.is_owned) return ''
  const diff = Math.round((brand.strength - own.strength) * 10) / 10
  if (Math.abs(diff) < 1) return 'هم‌تراز با شما'
  return diff > 0 ? `${diff.toLocaleString('fa-IR')} امتیاز قوی‌تر از شما` : `${Math.abs(diff).toLocaleString('fa-IR')} امتیاز ضعیف‌تر از شما`
}
