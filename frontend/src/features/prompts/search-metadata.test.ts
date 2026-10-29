import { describe, expect, it } from 'vitest'

import { hasNextPage, SEARCH_PAGE_SIZE, siteActionText, siteHref, usageCountLabel } from './search-metadata'

describe('usageCountLabel', () => {
  it('shows a badge only for repeated queries', () => {
    expect(usageCountLabel(1)).toBeNull()
    expect(usageCountLabel(0)).toBeNull()
    expect(usageCountLabel(Number.NaN)).toBeNull()
    expect(usageCountLabel(3)).toBe(`${(3).toLocaleString('fa-IR')} بار`)
  })
})

describe('siteActionText', () => {
  it('labels page actions and shows the find pattern', () => {
    expect(siteActionText({ action_type: 'open_page', pattern: null })).toBe('باز کردن صفحه')
    expect(siteActionText({ action_type: 'find_in_page', pattern: ' قیمت ' })).toBe('جستجو در صفحه: «قیمت»')
    expect(siteActionText({ action_type: 'find_in_page', pattern: null })).toBe('جستجو در صفحه')
    expect(siteActionText({ action_type: 'open_page', pattern: 'ignored' })).toBe('باز کردن صفحه')
  })
})

describe('siteHref', () => {
  it('only links http and https urls', () => {
    expect(siteHref({ url: 'https://parspack.com/blog' })).toBe('https://parspack.com/blog')
    expect(siteHref({ url: 'javascript:alert(1)' })).toBeNull()
  })
})

describe('hasNextPage', () => {
  it('uses the shared page size', () => {
    expect(SEARCH_PAGE_SIZE).toBe(50)
    expect(hasNextPage(1, 50)).toBe(false)
    expect(hasNextPage(1, 51)).toBe(true)
    expect(hasNextPage(2, 101, 50)).toBe(true)
    expect(hasNextPage(3, 101, 50)).toBe(false)
  })
})
