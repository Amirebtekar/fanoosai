import type { ProjectSearchedSite } from '@/lib/api'
import { actionLabel, safeHttpUrl } from './run-metadata'

export const SEARCH_PAGE_SIZE = 50

export function usageCountLabel(count: number): string | null {
  return Number.isFinite(count) && count > 1 ? `${Math.round(count).toLocaleString('fa-IR')} بار` : null
}

export function siteActionText(site: Pick<ProjectSearchedSite, 'action_type' | 'pattern'>): string {
  const label = actionLabel(site.action_type)
  const pattern = typeof site.pattern === 'string' ? site.pattern.trim() : ''
  return site.action_type === 'find_in_page' && pattern ? `${label}: «${pattern}»` : label
}

export function siteHref(site: Pick<ProjectSearchedSite, 'url'>): string | null {
  return safeHttpUrl(site.url)
}

export function hasNextPage(page: number, total: number, pageSize = SEARCH_PAGE_SIZE): boolean {
  return page * pageSize < total
}
