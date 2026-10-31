import { describe, expect, it } from 'vitest'

import type { PromptLeaderItem } from '@/lib/api'
import { appearancesLabel, formatRank, ownStatusLabel, splitPromptLeaders } from './prompt-leaders-data'

const leader = { brand_id: 1, brand: 'arvan', domain: null, average_rank: 1.1, appearances: 30 }

function item(own: PromptLeaderItem['own'], ownIsLeader = false): PromptLeaderItem {
  return { prompt_id: 1, prompt: 'p', total_runs: 32, leader, own, own_is_leader: ownIsLeader }
}

describe('prompt leaders data', () => {
  it('describes the own brand position', () => {
    expect(ownStatusLabel(item(null))).toBe('در پاسخ‌ها دیده نشده‌اید')
    expect(ownStatusLabel(item({ ...leader, brand_id: 2, appearances: 3, position: null, eligible: false }))).toBe('کم دیده شده‌اید (۳ از ۳۲ پاسخ)')
    expect(ownStatusLabel(item({ ...leader, brand_id: 2, position: 3, eligible: true }))).toBe('رتبه ۳ از برندهای پرتکرار')
    expect(ownStatusLabel(item({ ...leader, brand_id: 2, position: 2, eligible: true }), 'en-US')).toBe('رتبه 2 از برندهای پرتکرار')
  })

  it('splits prompts by leadership keeping order and formats numbers', () => {
    const leading = item({ ...leader, position: 1, eligible: true }, true)
    const behind = item(null)
    expect(splitPromptLeaders([behind, leading])).toEqual({ behind: [behind], leading: [leading] })
    expect(formatRank(1.1, 'en-US')).toBe('1.10')
    expect(appearancesLabel(18, 20, 'en-US')).toBe('18 از 20 پاسخ')
  })
})
