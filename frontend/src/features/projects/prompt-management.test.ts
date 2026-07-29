import { describe, expect, it } from 'vitest'

import { promptLines } from './prompt-management'

describe('promptLines', () => {
  it('makes one prompt from every non-empty line', () => {
    expect(promptLines('  اول  \n\nدوم\r\n  سوم ')).toEqual(['اول', 'دوم', 'سوم'])
  })
})
