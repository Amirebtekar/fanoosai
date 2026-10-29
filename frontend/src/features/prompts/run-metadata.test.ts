import { describe, expect, it } from 'vitest'

import { actionLabel, actionRows, citationRows, costCoverageLabel, formatCount, formatToman, formatUsd, NOT_RECORDED, safeHttpUrl, searchQueries, tokenParts } from './run-metadata'

describe('formatToman', () => {
  it('formats cost in Persian digits with the unit', () => {
    expect(formatToman(97399.2)).toBe(`${(97399).toLocaleString('fa-IR')} تومان`)
    expect(formatToman(0)).toBe(`${(0).toLocaleString('fa-IR')} تومان`)
  })

  it('reports missing cost as not recorded', () => {
    expect(formatToman(null)).toBe(NOT_RECORDED)
    expect(formatToman(undefined)).toBe(NOT_RECORDED)
    expect(formatToman(Number.NaN)).toBe(NOT_RECORDED)
  })
})

describe('formatCount and formatUsd', () => {
  it('formats counts and missing values', () => {
    expect(formatCount(43545)).toBe((43545).toLocaleString('fa-IR'))
    expect(formatCount(null)).toBe(NOT_RECORDED)
  })

  it('formats dollars or hides them', () => {
    expect(formatUsd(0.35894305)).toBe('$0.3589')
    expect(formatUsd(null)).toBeNull()
  })

  it('labels cost coverage', () => {
    expect(costCoverageLabel(3, 10)).toBe(`${(3).toLocaleString('fa-IR')} از ${(10).toLocaleString('fa-IR')} اجرا`)
  })
})

describe('tokenParts', () => {
  it('keeps only recorded token counts in a fixed order', () => {
    expect(tokenParts({ prompt_tokens: 100, completion_tokens: 20, reasoning_tokens: null, cached_tokens: 0, total_tokens: 120 }).map(part => part.label))
      .toEqual(['ورودی', 'خروجی', 'کش', 'مجموع'])
    expect(tokenParts({})).toEqual([])
  })
})

describe('safeHttpUrl', () => {
  it('accepts only http and https URLs', () => {
    expect(safeHttpUrl('https://sibchob.ir/')).toBe('https://sibchob.ir/')
    expect(safeHttpUrl('http://example.com/a')).toBe('http://example.com/a')
    expect(safeHttpUrl('javascript:alert(1)')).toBeNull()
    expect(safeHttpUrl('not a url')).toBeNull()
    expect(safeHttpUrl(5)).toBeNull()
  })
})

describe('actionRows', () => {
  it('labels search, open_page and find_in_page actions', () => {
    const rows = actionRows([
      { type: 'search', queries: ['q1', 'q2'] },
      { type: 'search', query: 'single' },
      { type: 'open_page', url: 'https://openai.com/news/' },
      { type: 'find_in_page', pattern: 'نماد', url: 'https://sibchob.ir/' },
    ])
    expect(rows.map(row => [row.label, row.detail, row.url])).toEqual([
      ['جستجو', 'q1، q2', null],
      ['جستجو', 'single', null],
      ['باز کردن صفحه', '', 'https://openai.com/news/'],
      ['جستجو در صفحه', '«نماد»', 'https://sibchob.ir/'],
    ])
  })

  it('drops unsafe urls and empty non-search actions', () => {
    expect(actionRows([{ type: 'open_page', url: 'javascript:alert(1)' }, { type: 'open_page' }])).toEqual([])
    expect(actionRows(null)).toEqual([])
    expect(actionLabel('custom')).toBe('custom')
  })
})

describe('citationRows and searchQueries', () => {
  it('uses titles, falls back to url, and dedupes', () => {
    expect(citationRows([
      { url: 'https://parspack.com/', title: 'پارس پک' },
      { url: 'https://sibchob.ir/', title: null },
      { url: 'https://parspack.com/', title: 'again' },
      { url: 'data:text/html,x', title: 'bad' },
    ])).toEqual([
      { url: 'https://parspack.com/', label: 'پارس پک' },
      { url: 'https://sibchob.ir/', label: 'https://sibchob.ir/' },
    ])
    expect(citationRows(undefined)).toEqual([])
  })

  it('dedupes queries and drops blanks', () => {
    expect(searchQueries(['a', 'b', 'a', ' '])).toEqual(['a', 'b'])
    expect(searchQueries(null)).toEqual([])
  })
})
