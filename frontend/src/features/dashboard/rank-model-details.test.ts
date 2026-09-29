import { describe, expect, it } from 'vitest'

import { summarizeModelRanks, tehranBounds, tehranReportDays } from './rank-model-details'

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
