import type { PromptHistoryItem, RunCitation, WebSearchAction } from '@/lib/api'

export const NOT_RECORDED = 'ثبت نشده'

const ACTION_LABELS: Record<string, string> = {
  search: 'جستجو',
  open_page: 'باز کردن صفحه',
  find_in_page: 'جستجو در صفحه',
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

export function formatCount(value: number | null | undefined): string {
  return isFiniteNumber(value) ? Math.round(value).toLocaleString('fa-IR') : NOT_RECORDED
}

export function formatToman(value: number | null | undefined): string {
  if (!isFiniteNumber(value)) return NOT_RECORDED
  return `${Math.round(value).toLocaleString('fa-IR')} تومان`
}

export function formatUsd(value: number | null | undefined): string | null {
  if (!isFiniteNumber(value)) return null
  return `$${value.toLocaleString('en-US', { maximumFractionDigits: 4 })}`
}

export function actionLabel(type: string): string {
  return ACTION_LABELS[type] ?? type
}

export function safeHttpUrl(value: unknown): string | null {
  if (typeof value !== 'string') return null
  try {
    const url = new URL(value)
    return url.protocol === 'http:' || url.protocol === 'https:' ? value : null
  } catch {
    return null
  }
}

export interface ActionRow { key: string; label: string; detail: string; url: string | null }

export function actionRows(actions: WebSearchAction[] | null | undefined): ActionRow[] {
  if (!Array.isArray(actions)) return []
  return actions.flatMap((action, index) => {
    if (!action || typeof action.type !== 'string') return []
    const url = safeHttpUrl(action.url)
    const queries = Array.isArray(action.queries) ? action.queries.filter(item => typeof item === 'string' && item) : []
    const query = typeof action.query === 'string' ? action.query : ''
    const pattern = typeof action.pattern === 'string' ? action.pattern : ''
    const parts = action.type === 'search' ? (queries.length ? queries : query ? [query] : []) : [pattern && `«${pattern}»`].filter(Boolean)
    const detail = parts.join('، ')
    if (!url && !detail && action.type !== 'search') return []
    return [{ key: `${index}-${action.type}`, label: actionLabel(action.type), detail, url }]
  })
}

export function citationRows(citations: RunCitation[] | null | undefined): { url: string; label: string }[] {
  if (!Array.isArray(citations)) return []
  const seen = new Set<string>()
  return citations.flatMap(citation => {
    const url = safeHttpUrl(citation?.url)
    if (!url || seen.has(url)) return []
    seen.add(url)
    const title = typeof citation.title === 'string' ? citation.title.trim() : ''
    return [{ url, label: title || url }]
  })
}

export function searchQueries(queries: string[] | null | undefined): string[] {
  if (!Array.isArray(queries)) return []
  return [...new Set(queries.filter(item => typeof item === 'string' && item.trim()))]
}

export interface TokenPart { label: string; value: string }

export function tokenParts(run: Pick<PromptHistoryItem, 'prompt_tokens' | 'completion_tokens' | 'reasoning_tokens' | 'cached_tokens' | 'total_tokens'>): TokenPart[] {
  const parts: [string, number | null | undefined][] = [
    ['ورودی', run.prompt_tokens],
    ['خروجی', run.completion_tokens],
    ['استدلال', run.reasoning_tokens],
    ['کش', run.cached_tokens],
    ['مجموع', run.total_tokens],
  ]
  return parts.filter(([, value]) => isFiniteNumber(value)).map(([label, value]) => ({ label, value: formatCount(value) }))
}

export function costCoverageLabel(withCost: number, total: number): string {
  return `${withCost.toLocaleString('fa-IR')} از ${total.toLocaleString('fa-IR')} اجرا`
}
