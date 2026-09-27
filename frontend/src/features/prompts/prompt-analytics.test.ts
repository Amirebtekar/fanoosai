import { describe, expect, it } from 'vitest'

import { defaultTrendSelection, modelResponseText } from './prompt-analytics'
import { buildRankTableRows, rankReportDays, tehranDateKey } from './rank-report-utils'

describe('modelResponseText', () => {
  it('shows only the OpenAI response content', () => {
    expect(modelResponseText(JSON.stringify({
      choices: [{ message: { content: 'پاسخ مدل' } }],
    }))).toBe('پاسخ مدل')
  })

  it('shows only the Gemini response content', () => {
    expect(modelResponseText(JSON.stringify({
      candidates: [{ content: { parts: [{ text: 'پاسخ Gemini' }] } }],
    }))).toBe('پاسخ Gemini')
  })

  it('shows only Claude text blocks', () => {
    expect(modelResponseText(JSON.stringify({
      content: [{ type: 'text', text: '## پاسخ Claude' }, { type: 'tool_use', name: 'search' }],
    }))).toBe('## پاسخ Claude')
  })

  it('extracts OpenAI Responses API output text', () => {
    expect(modelResponseText(JSON.stringify({
      id: 'resp_1',
      output: [
        { type: 'reasoning' },
        { type: 'message', content: [{ type: 'output_text', text: 'پاسخ Responses' }] },
      ],
    }))).toBe('پاسخ Responses')
  })
})

describe('defaultTrendSelection', () => {
  it('selects one model and excludes every other model from the chart', () => {
    const selection = defaultTrendSelection({
      prompt_id: 7,
      items: [
        { ai_model_id: 2, ai_model: 'model two', brand_id: 10, brand: 'A', points: [], trend: 'flat' },
        { ai_model_id: 3, ai_model: 'model three', brand_id: 11, brand: 'B', points: [], trend: 'flat' },
        { ai_model_id: 2, ai_model: 'model two', brand_id: 12, brand: 'C', points: [], trend: 'flat' },
      ],
    })

    expect(selection.modelId).toBe('2')
    expect(selection.trends.items.map(item => item.ai_model_id)).toEqual([2, 2])
  })
})

describe('rank report filters and daily ranks', () => {
  it('uses Tehran calendar days and returns newest days first', () => {
    expect(tehranDateKey('2026-09-26T20:30:00.000Z')).toBe('2026-09-27')
    expect(rankReportDays(new Date(2026, 8, 25), new Date(2026, 8, 27))).toEqual([
      '2026-09-27',
      '2026-09-26',
      '2026-09-25',
    ])
  })

  it('keeps the last rank per Tehran day and applies model/brand/text filters', () => {
    const items = [
      {
        ai_model_id: 5,
        ai_model: 'model A',
        brand_id: 10,
        brand: 'پارس‌پک',
        domain: 'parspack.com',
        points: [
          { date: '2026-09-24T20:31:00.000Z', rank: 2, ai_run_id: 1 },
          { date: '2026-09-25T21:00:00.000Z', rank: 1, ai_run_id: 2 },
          { date: '2026-09-26T20:00:00.000Z', rank: 3, ai_run_id: 3 },
        ],
        trend: 'down' as const,
      },
      { ai_model_id: 6, ai_model: 'model B', brand_id: 11, brand: 'Other', points: [], trend: 'flat' as const },
    ]

    const rows = buildRankTableRows(items, ['2026-09-26', '2026-09-25'], '2026-09-26', '2026-09-25', '5', '10', 'parspack')

    expect(rows).toHaveLength(1)
    expect(rows[0]).toMatchObject({ average: 2.5, change: 1, today: 3, yesterday: 2 })
    expect(rows[0].daily).toEqual({ '2026-09-25': 2, '2026-09-26': 3 })
  })
})
