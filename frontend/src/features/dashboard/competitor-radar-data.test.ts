import { describe, expect, it } from 'vitest'

import type { CompetitorRadarBrand } from '@/lib/api'
import { OWN_BRAND_COLOR, RADAR_AXES, compareWithOwn, radarRows, radarSeries } from './competitor-radar-data'

function brand(id: number, name: string, strength: number, isOwned = false): CompetitorRadarBrand {
  return {
    brand_id: id, brand: name, domain: null, is_owned: isOwned, strength,
    visibility: strength, rank_score: 50, first_place: 10, model_coverage: 80, prompt_coverage: 100,
    appearances: 3, average_rank: 2, first_place_count: 1, models: 4, prompts: 1,
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
    expect(rows[4]).toEqual({ axis: 'پوشش پرامپت‌ها', brand_1: 100 })
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
