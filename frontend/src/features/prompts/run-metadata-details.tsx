import { ExternalLink } from 'lucide-react'
import type { PromptHistoryItem } from '@/lib/api'
import { actionRows, citationRows, formatCount, formatToman, formatUsd, searchQueries, tokenParts } from './run-metadata'

export function RunMetadataDetails({ run }: { run: PromptHistoryItem }) {
  const tokens = tokenParts(run)
  const queries = searchQueries(run.web_search_queries)
  const actions = actionRows(run.web_search_actions)
  const citations = citationRows(run.citations)
  const usd = formatUsd(run.cost_usd)
  const searchCount = typeof run.web_search_count === 'number' ? run.web_search_count : null

  return (
    <details className='group border-t-2 border-border bg-muted/10 text-sm' dir='rtl'>
      <summary className='cursor-pointer select-none px-4 py-3 text-xs font-bold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'>
        جستجوها و منابع
        {searchCount != null && <span className='ms-2 font-medium text-muted-text'>({formatCount(searchCount)} جستجو)</span>}
      </summary>
      <div className='space-y-4 px-4 pb-4'>
        <dl className='grid gap-x-6 gap-y-2 text-xs sm:grid-cols-2'>
          <div className='flex flex-wrap gap-1'>
            <dt className='font-bold'>هزینه:</dt>
            <dd>{formatToman(run.cost_irt)}{usd && <span className='ms-2 text-muted-text' dir='ltr'>({usd})</span>}</dd>
          </div>
          <div className='flex flex-wrap gap-1'>
            <dt className='font-bold'>تعداد جستجوی وب:</dt>
            <dd>{formatCount(searchCount)}</dd>
          </div>
          <div className='flex flex-wrap gap-1 sm:col-span-2'>
            <dt className='font-bold'>توکن‌ها:</dt>
            <dd>{tokens.length ? tokens.map(part => `${part.label} ${part.value}`).join(' / ') : 'ثبت نشده'}</dd>
          </div>
        </dl>

        {queries.length > 0 && (
          <section className='space-y-2'>
            <h4 className='text-xs font-black'>عبارت‌های جستجو</h4>
            <ul className='flex flex-wrap gap-2'>
              {queries.map(query => <li key={query} className='rounded border border-border/70 bg-background px-2 py-1 text-xs' dir='auto'>{query}</li>)}
            </ul>
          </section>
        )}

        {actions.length > 0 && (
          <section className='space-y-2'>
            <h4 className='text-xs font-black'>سایت‌های بازشده و جستجوشده</h4>
            <ol className='max-h-60 space-y-1.5 overflow-auto text-xs'>
              {actions.map(action => (
                <li key={action.key} className='flex flex-wrap items-baseline gap-2'>
                  <span className='shrink-0 rounded bg-primary/10 px-1.5 py-0.5 font-bold text-primary'>{action.label}</span>
                  {action.url && <a className='break-all text-primary underline underline-offset-4' href={action.url} target='_blank' rel='noopener noreferrer' dir='ltr'>{action.url}</a>}
                  {action.detail && <span className='break-words text-muted-text' dir='auto'>{action.detail}</span>}
                </li>
              ))}
            </ol>
          </section>
        )}

        {citations.length > 0 && (
          <section className='space-y-2'>
            <h4 className='text-xs font-black'>منابع استنادشده</h4>
            <ol className='list-decimal space-y-1.5 ps-5 text-xs'>
              {citations.map(citation => (
                <li key={citation.url}>
                  <a className='inline-flex max-w-full items-start gap-1 break-all text-primary underline underline-offset-4' href={citation.url} target='_blank' rel='noopener noreferrer' title={citation.url} dir='auto'>
                    <span>{citation.label}</span>
                    <ExternalLink className='mt-0.5 size-3 shrink-0' aria-hidden='true' />
                    <span className='sr-only'>در پنجره جدید باز می‌شود</span>
                  </a>
                </li>
              ))}
            </ol>
          </section>
        )}
      </div>
    </details>
  )
}
