import { describe, expect, it } from 'vitest'

import type { AIModelRead } from '@/lib/api'
import { filterModels, groupModelsByProvider, modelMatches, providerOf } from './model-picker-utils'
import { promptLines, runAvailablePromptModels } from './prompt-management'

const model = (partial: Partial<AIModelRead> & Pick<AIModelRead, 'id' | 'name'>): AIModelRead => ({
  provider: 'Gateway',
  model_key: partial.name,
  is_active: true,
  ...partial,
})

describe('promptLines', () => {
  it('makes one prompt from every non-empty line', () => {
    expect(promptLines('  اول  \n\nدوم\r\n  سوم ')).toEqual(['اول', 'دوم', 'سوم'])
  })
})

describe('runAvailablePromptModels', () => {
  it('starts every available model without waiting for the previous one', async () => {
    const started: number[] = []
    const finish: Array<() => void> = []

    const running = runAvailablePromptModels([
      { model_id: 1, model_name: 'one', can_run: true },
      { model_id: 2, model_name: 'two', can_run: true },
      { model_id: 3, model_name: 'done', can_run: false },
    ], modelId => new Promise<void>(resolve => {
      started.push(modelId)
      finish.push(resolve)
    }))

    await Promise.resolve()
    expect(started).toEqual([1, 2])
    finish.forEach(resolve => resolve())
    await running
  })
})

describe('modelMatches', () => {
  it('matches name, model key and provider case-insensitively', () => {
    const gpt = model({ id: 1, name: 'openai/gpt-5', provider: 'OpenAI', model_key: 'openai/gpt-5' })
    expect(modelMatches(gpt, 'GPT')).toBe(true)
    expect(modelMatches(gpt, 'openai')).toBe(true)
    expect(modelMatches(gpt, '  ')).toBe(true)
    expect(modelMatches(gpt, 'claude')).toBe(false)
  })
})

describe('filterModels', () => {
  it('keeps only models matching the query', () => {
    const models = [
      model({ id: 1, name: 'openai/gpt-5' }),
      model({ id: 2, name: 'anthropic/claude-sonnet-4.6' }),
    ]
    expect(filterModels(models, 'claude').map(item => item.id)).toEqual([2])
    expect(filterModels(models, '')).toHaveLength(2)
  })
})

describe('providerOf / groupModelsByProvider', () => {
  it('falls back to the model key prefix when provider is generic', () => {
    expect(providerOf(model({ id: 1, name: 'google/gemini-3.1-pro', provider: 'Gateway' }))).toBe('google')
    expect(providerOf(model({ id: 2, name: 'x', provider: 'Anthropic' }))).toBe('Anthropic')
  })

  it('groups by provider and sorts groups and names', () => {
    const groups = groupModelsByProvider([
      model({ id: 1, name: 'openai/gpt-5-mini', provider: 'OpenAI' }),
      model({ id: 2, name: 'anthropic/claude-haiku', provider: 'Anthropic' }),
      model({ id: 3, name: 'openai/gpt-5', provider: 'OpenAI' }),
    ])

    expect(groups.map(group => group.provider)).toEqual(['Anthropic', 'OpenAI'])
    expect(groups[1].models.map(item => item.name)).toEqual(['openai/gpt-5', 'openai/gpt-5-mini'])
  })
})
