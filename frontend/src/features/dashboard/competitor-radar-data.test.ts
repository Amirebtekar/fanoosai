import { describe, expect, it } from 'vitest'

import type { CompetitorRadarBrand } from '@/lib/api'
import { OWN_BRAND_COLOR, RADAR_AXES, RADAR_SVG, compareWithOwn, radarPoint, radarSvg, topThreeDetails, radarRows, radarSeries } from './competitor-radar-data'

function brand(id: number, name: string, strength: number, isOwned = false): CompetitorRadarBrand {
  return {
    brand_id: id, brand: name, domain: null, is_owned: isOwned, strength,
    visibility: strength, rank_score: 50, top_three: 66.7, model_coverage: 80, prompt_coverage: 100,
    appearances: 3, average_rank: 2, top_three_count: 2, models: 4, prompts: 1,
  }
}

describe('competitor radar data', () => {
  it('colours the own brand orange and competitors in order', () => {
    const series = radarSeries([brand(1, 'a', 90), brand(2, 'me', 50, true), brand(3, 'b', 40)])
    expect(series.map(item => item.color)).toEqual(['#2563eb', OWN_BRAND_COLOR, '#16a34a'])
    expect(series.map(item => item.key)).toEqual(['brand_1', 'brand_2', 'brand_3'])
  })

  it('builds one row per axis with only the visible brands', () => {
    const series = radarSeries([brand(1, 'a', 90), brand(2, 'b', 40)])
    const rows = radarRows(series, new Set(['brand_1']))
    expect(rows).toHaveLength(RADAR_AXES.length)
    expect(rows[0]).toEqual({ axis: 'دیده‌شدن', brand_1: 90 })
    expect(rows[2]).toEqual({ axis: 'حضور در ۳ رتبه اول', brand_1: 66.7 })
    expect(RADAR_AXES.map(axis => axis.key)).not.toContain('first_place')
    expect(rows[4]).toEqual({ axis: 'پوشش پرامپت‌ها', brand_1: 100 })
  })

  it('shows the raw top-three percentage and appearance counts including no data', () => {
    const item = brand(1, 'a', 50)
    expect(topThreeDetails(item)).toBe('حضور در ۳ رتبه اول: ۶۶٫۷٪ (۲ از ۳ حضور)')
    expect(topThreeDetails({ ...item, top_three: 0, top_three_count: 0, appearances: 0 })).toBe('حضور در ۳ رتبه اول: ۰٪ (۰ از ۰ حضور)')
    expect(RADAR_AXES[2].hint).toContain('بدون کاهش بابت حجم نمونه')
    expect(radarRows([], new Set()).every(row => Object.keys(row).length === 1)).toBe(true)
  })

  it('draws one polygon per brand with own brand orange and thicker', () => {
    const svg = radarSvg([brand(1, 'a', 90), brand(2, 'me', 50, true), brand(3, 'b', 40)])
    expect(svg.startsWith('<svg')).toBe(true)
    expect(svg.match(/<polygon data-brand=/g)).toHaveLength(3)
    expect(svg).toMatch(new RegExp(`data-brand="2"[^>]*fill="${OWN_BRAND_COLOR}" fill-opacity="0.28" stroke="${OWN_BRAND_COLOR}" stroke-width="3"`))
    expect(svg).toContain('data-brand="1"')
    expect(svg).toMatch(/data-brand="1"[^>]*fill="#2563eb" fill-opacity="0.08"/)
    for (const axis of RADAR_AXES) expect(svg).toContain(`>${axis.label}</text>`)
    expect(svg).toContain('me (شما) — قدرت 50')
  })

  it('maps 100 to the outer radius and 0 to the centre', () => {
    const svg = radarSvg([{ ...brand(1, 'a', 0), visibility: 100, rank_score: 0, top_three: 0, model_coverage: 0, prompt_coverage: 0 }])
    const centre = `${RADAR_SVG.centerX},${RADAR_SVG.centerY}`
    const top = `${RADAR_SVG.centerX},${RADAR_SVG.centerY - RADAR_SVG.radius}`
    expect(svg).toContain(`points="${top} ${centre} ${centre} ${centre} ${centre}"`)
    const outer = radarPoint(1, 100)
    expect(Math.hypot(outer.x - RADAR_SVG.centerX, outer.y - RADAR_SVG.centerY)).toBeCloseTo(RADAR_SVG.radius, 0)
    expect(radarPoint(3, 0)).toEqual({ x: RADAR_SVG.centerX, y: RADAR_SVG.centerY })
  })

  it('escapes brand names and handles empty and tiny inputs', () => {
    const svg = radarSvg([brand(1, '<script>alert(1)</script>', 30)])
    expect(svg).not.toContain('<script>')
    expect(svg).toContain('&lt;script&gt;alert(1)&lt;/script&gt;')
    expect(svg.match(/<polygon data-brand=/g)).toHaveLength(1)
    expect(radarSvg([brand(1, 'a', 30), brand(2, 'b', 20)]).match(/<polygon data-brand=/g)).toHaveLength(2)
    expect(radarSvg([])).toBe('')
  })

  it('explains each competitor relative to the own brand', () => {
    const own = brand(9, 'me', 50, true)
    expect(compareWithOwn(brand(1, 'a', 72.5), own)).toBe('۲۲٫۵ امتیاز قوی‌تر از شما')
    expect(compareWithOwn(brand(2, 'b', 30), own)).toBe('۲۰ امتیاز ضعیف‌تر از شما')
    expect(compareWithOwn(brand(3, 'c', 50.4), own)).toBe('هم‌تراز با شما')
    expect(compareWithOwn(own, own)).toBe('')
    expect(compareWithOwn(brand(4, 'd', 10), undefined)).toBe('')
  })
})
