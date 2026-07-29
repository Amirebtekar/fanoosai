import { describe, expect, it } from 'vitest'

import { modelResponseText } from './prompt-analytics'

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
