import { useEffect, useState } from 'react'
import { getCostSummary, type CostSummary } from '@/lib/api'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { costCoverageLabel, formatCount, formatToman, formatUsd } from '@/features/prompts/run-metadata'

export function CostSummaryCard({ projectId }: { projectId: string }) {
  const [days, setDays] = useState<7 | 30>(7)
  const [result, setResult] = useState<{ key: string; data?: CostSummary; error?: boolean } | null>(null)

  const requestKey = `${projectId}:${days}`
  useEffect(() => {
    if (!projectId) return
    getCostSummary(Number(projectId), days)
      .then(data => setResult({ key: requestKey, data }))
      .catch(() => setResult({ key: requestKey, error: true }))
  }, [projectId, days, requestKey])

  const current = result?.key === requestKey ? result : null
  const data = current?.data
  const usd = data && data.runs_with_cost > 0 ? formatUsd(data.total_cost_usd) : null

  return (
    <Card className='mt-6 border-border shadow-[6px_6px_0_var(--color-shadow)]'>
      <CardHeader className='flex flex-row flex-wrap items-start justify-between gap-3'>
        <div className='space-y-2'>
          <CardTitle className='text-lg font-black'>هزینه و مصرف مدل‌ها</CardTitle>
          <CardDescription>جمع هزینه، توکن و جستجوهای وب اجراهای موفق این پروژه.</CardDescription>
        </div>
        <Select value={String(days)} onValueChange={value => setDays(Number(value) as 7 | 30)}>
          <SelectTrigger className='border-border bg-background sm:w-40' aria-label='بازهٔ هزینه'><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value='7'>۷ روز گذشته</SelectItem>
            <SelectItem value='30'>۳۰ روز گذشته</SelectItem>
          </SelectContent>
        </Select>
      </CardHeader>
      <CardContent className='space-y-4'>
        {!current && <Skeleton className='h-28 w-full bg-accent' />}
        {current?.error && <p role='alert' className='text-sm font-bold text-red-600'>دریافت خلاصهٔ هزینه ممکن نشد.</p>}
        {data && (
          <>
            <div className='grid gap-3 sm:grid-cols-2 lg:grid-cols-4'>
              <div className='rounded-lg border border-border/70 bg-muted/20 p-3'>
                <p className='text-xs text-muted-text'>هزینهٔ کل</p>
                <p className='mt-1 font-black'>{data.runs_with_cost ? formatToman(data.total_cost_irt) : 'ثبت نشده'}</p>
                {usd && <p className='text-xs text-muted-text' dir='ltr'>{usd}</p>}
              </div>
              <div className='rounded-lg border border-border/70 bg-muted/20 p-3'>
                <p className='text-xs text-muted-text'>اجراهای دارای هزینه</p>
                <p className='mt-1 font-black'>{costCoverageLabel(data.runs_with_cost, data.total_runs)}</p>
              </div>
              <div className='rounded-lg border border-border/70 bg-muted/20 p-3'>
                <p className='text-xs text-muted-text'>توکن‌ها</p>
                <p className='mt-1 font-black'>{formatCount(data.total_tokens)}</p>
              </div>
              <div className='rounded-lg border border-border/70 bg-muted/20 p-3'>
                <p className='text-xs text-muted-text'>جستجوهای وب</p>
                <p className='mt-1 font-black'>{formatCount(data.web_search_count)}</p>
              </div>
            </div>
            {data.total_runs > data.runs_with_cost && (
              <p className='text-xs text-muted-text'>هزینهٔ اجراهای قدیمی ذخیره نشده است؛ از این پس هزینهٔ هر اجرا ثبت می‌شود.</p>
            )}
            {data.models.length > 0 ? (
              <div className='overflow-x-auto border border-border/70'>
                <table className='w-full min-w-[520px] text-right text-sm'>
                  <thead className='border-b-2 border-border bg-muted/30 text-muted-text'>
                    <tr><th scope='col' className='p-2'>مدل</th><th scope='col' className='p-2'>اجرا</th><th scope='col' className='p-2'>هزینه</th><th scope='col' className='p-2'>توکن</th><th scope='col' className='p-2'>جستجو</th></tr>
                  </thead>
                  <tbody>
                    {data.models.map(model => (
                      <tr key={model.ai_model} className='border-b border-border/60 last:border-0'>
                        <td className='p-2 font-bold' dir='ltr'>{model.ai_model}</td>
                        <td className='p-2 tabular-nums'>{formatCount(model.runs)}</td>
                        <td className='p-2 tabular-nums'>{model.cost_irt ? formatToman(model.cost_irt) : '—'}</td>
                        <td className='p-2 tabular-nums'>{model.total_tokens ? formatCount(model.total_tokens) : '—'}</td>
                        <td className='p-2 tabular-nums'>{model.web_search_count ? formatCount(model.web_search_count) : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <p className='py-4 text-center text-sm text-muted-text'>در این بازه اجرای موفقی ثبت نشده است.</p>}
          </>
        )}
      </CardContent>
    </Card>
  )
}
