import { describe, expect, it } from 'vitest'

import { promptLines, runAvailablePromptModels } from './prompt-management'

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
