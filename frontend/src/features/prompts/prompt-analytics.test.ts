import { describe, expect, it } from 'vitest'

import { defaultTrendSelection, modelResponseText } from './prompt-analytics'

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
