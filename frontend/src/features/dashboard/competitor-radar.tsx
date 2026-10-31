import { useEffect, useMemo, useState } from 'react'
import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer, Tooltip } from 'recharts'
import { getCompetitorRadar, type CompetitorRadar as CompetitorRadarData, type PromptRead } from '@/lib/api'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { RADAR_AXES, compareWithOwn, topThreeDetails, radarRows, radarSeries } from './competitor-radar-data'

export function CompetitorRadarCard({ projectId, prompts }: { projectId: string; prompts: PromptRead[] }) {
  const [days, setDays] = useState<7 | 30>(7)
  const [promptId, setPromptId] = useState('all')
  const [result, setResult] = useState<{ key: string; data?: CompetitorRadarData; error?: boolean } | null>(null)
  const [hidden, setHidden] = useState<Set<string>>(new Set())

  const requestKey = `${projectId}:${promptId}:${days}`
  useEffect(() => {
    if (!projectId) return
    getCompetitorRadar(Number(projectId), { days, prompt_id: promptId === 'all' ? undefined : Number(promptId), limit: 6 })
      .then(data => setResult({ key: requestKey, data }))
      .catch(() => setResult({ key: requestKey, error: true }))
  }, [projectId, promptId, days, requestKey])

  const current = result?.key === requestKey ? result : null
  const series = useMemo(() => radarSeries(current?.data?.brands ?? []), [current])
  // Hidden keys of brands no longer in the series are ignored, so no reset effect is needed.
  const visible = useMemo(() => {
    const shown = series.filter(item => !hidden.has(item.key))
    return new Set((shown.length ? shown : series).map(item => item.key))
  }, [series, hidden])
  const rows = useMemo(() => radarRows(series, visible), [series, visible])
  const own = series.find(item => item.is_owned)
  const strongest = series.find(item => !item.is_owned)

  const toggle = (key: string) => setHidden(previous => {
    const next = new Set(previous)
    if (next.has(key)) next.delete(key)
    else if (visible.size > 1) next.add(key)
    return next
  })

  return (
    <Card className='mt-6 border-border shadow-[6px_6px_0_var(--color-shadow)]'>
      <CardHeader className='flex flex-row flex-wrap items-start justify-between gap-3'>
        <div className='space-y-2'>
          <CardTitle className='text-lg font-black'>رادار رقبا</CardTitle>
          <CardDescription>قوی‌ترین رقبا در کنار برند شما روی پنج شاخص؛ هر محور از ۰ تا ۱۰۰ است و بیشتر یعنی قوی‌تر.</CardDescription>
        </div>
        <div className='grid w-full gap-3 sm:w-auto sm:grid-cols-2'>
          <Select value={promptId} onValueChange={setPromptId} disabled={!projectId}>
            <SelectTrigger className='border-border bg-background sm:w-64' aria-label='پرامپت'><SelectValue placeholder='همهٔ پرامپت‌ها' /></SelectTrigger>
            <SelectContent>
              <SelectItem value='all'>همهٔ پرامپت‌ها</SelectItem>
              {prompts.map(prompt => <SelectItem key={prompt.id} value={String(prompt.id)}>{prompt.text.slice(0, 55)}{prompt.text.length > 55 ? '...' : ''}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={String(days)} onValueChange={value => setDays(Number(value) as 7 | 30)}>
            <SelectTrigger className='border-border bg-background' aria-label='بازه'><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value='7'>۷ روز گذشته</SelectItem>
              <SelectItem value='30'>۳۰ روز گذشته</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </CardHeader>
      <CardContent className='space-y-5'>
        {projectId && !current && <Skeleton className='h-80 w-full bg-accent' />}
        {current?.error && <p role='alert' className='text-sm font-bold text-red-600'>دریافت رادار رقبا ممکن نشد.</p>}
        {current?.data && series.length === 0 && <p className='py-6 text-center text-sm text-muted-text'>در این بازه هنوز برندی ثبت نشده است.</p>}
        {current?.data && series.length > 0 && (
          <>
            {strongest && (
              <div className='grid gap-3 sm:grid-cols-3'>
                <div className='rounded-lg border border-border/70 bg-muted/20 p-3'>
                  <p className='text-xs text-muted-text'>قوی‌ترین رقیب</p>
                  <p className='mt-1 font-black'>{strongest.brand}</p>
                  <p className='text-xs text-muted-text'>امتیاز قدرت {strongest.strength.toLocaleString('fa-IR')}</p>
                </div>
                <div className='rounded-lg border border-border/70 bg-muted/20 p-3'>
                  <p className='text-xs text-muted-text'>برند شما</p>
                  <p className='mt-1 font-black'>{own ? own.brand : 'تعریف نشده'}</p>
                  <p className='text-xs text-muted-text'>{own ? `امتیاز قدرت ${own.strength.toLocaleString('fa-IR')}` : 'برند خود را در تنظیمات پروژه اضافه کنید'}</p>
                </div>
                <div className='rounded-lg border border-border/70 bg-muted/20 p-3'>
                  <p className='text-xs text-muted-text'>جایگاه شما</p>
                  <p className='mt-1 font-black'>{own ? `${(series.findIndex(item => item.is_owned) + 1).toLocaleString('fa-IR')} از ${series.length.toLocaleString('fa-IR')}` : '—'}</p>
                  <p className='text-xs text-muted-text'>بر اساس {current.data.total_runs.toLocaleString('fa-IR')} پاسخ</p>
                </div>
              </div>
            )}
            <div className='grid gap-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]'>
              <div className='h-[380px] w-full min-w-0' role='img' aria-label='نمودار راداری مقایسهٔ برند با رقبا' dir='ltr'>
                <ResponsiveContainer width='100%' height='100%'>
                  <RadarChart data={rows} outerRadius='72%' margin={{ top: 10, right: 30, bottom: 10, left: 30 }}>
                    <PolarGrid stroke='var(--border)' />
                    <PolarAngleAxis dataKey='axis' tick={{ fill: 'var(--foreground)', fontSize: 12, fontWeight: 700 }} />
                    <PolarRadiusAxis domain={[0, 100]} tickCount={5} angle={90} tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} axisLine={false} />
                    <Tooltip
                      contentStyle={{ background: 'var(--popover)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', color: 'var(--popover-foreground)', direction: 'rtl' }}
                      formatter={(value, name, entry) => {
                        const brand = series.find(item => item.key === entry.dataKey)
                        return [entry.payload?.axis === 'حضور در ۳ رتبه اول' && brand ? topThreeDetails(brand) : Number(value).toLocaleString('fa-IR'), name]
                      }}
                    />
                    {series.filter(item => visible.has(item.key)).map(item => (
                      <Radar
                        key={item.key}
                        name={item.brand}
                        dataKey={item.key}
                        stroke={item.color}
                        fill={item.color}
                        fillOpacity={item.is_owned ? 0.28 : 0.08}
                        strokeWidth={item.is_owned ? 3 : 2}
                        isAnimationActive={false}
                      />
                    ))}
                  </RadarChart>
                </ResponsiveContainer>
              </div>
              <div className='space-y-2'>
                <p className='text-xs text-muted-text'>برای پنهان یا نمایش هر برند روی آن کلیک کنید.</p>
                {series.map((item, index) => (
                  <button
                    key={item.key}
                    type='button'
                    aria-pressed={visible.has(item.key)}
                    onClick={() => toggle(item.key)}
                    className={`flex w-full items-center gap-3 rounded-lg border px-3 py-2 text-right transition-opacity focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${item.is_owned ? 'border-orange-400 bg-orange-50/40 dark:bg-orange-950/20' : 'border-border/70 bg-muted/20'} ${visible.has(item.key) ? '' : 'opacity-40'}`}
                  >
                    <span className='w-5 shrink-0 text-xs font-bold tabular-nums text-muted-text'>{(index + 1).toLocaleString('fa-IR')}</span>
                    <span aria-hidden='true' className='size-3 shrink-0 rounded-full' style={{ backgroundColor: item.color }} />
                    <span className='min-w-0 flex-1'>
                      <span className='block truncate text-sm font-bold'>{item.brand}{item.is_owned && <span className='ms-2 text-xs font-medium text-orange-600'>(شما)</span>}</span>
                      <span className='block truncate text-xs text-muted-text'>
                        در {item.appearances.toLocaleString('fa-IR')} از {current.data!.total_runs.toLocaleString('fa-IR')} پاسخ · میانگین رتبه {item.average_rank?.toLocaleString('fa-IR', { maximumFractionDigits: 2 }) ?? '—'}
                        {compareWithOwn(item, own) && ` · ${compareWithOwn(item, own)}`}
                      </span>
                      <span className='block text-xs text-muted-text'>{topThreeDetails(item)}</span>
                    </span>
                    <span className='shrink-0 text-lg font-black tabular-nums'>{item.strength.toLocaleString('fa-IR')}</span>
                  </button>
                ))}
              </div>
            </div>
            <details className='rounded-lg border border-border/70 p-3 text-xs text-muted-text'>
              <summary className='cursor-pointer font-bold text-foreground'>شاخص‌ها چطور حساب می‌شوند؟</summary>
              <ul className='mt-2 list-disc space-y-1 ps-5'>
                {RADAR_AXES.map(axis => <li key={axis.key}><span className='font-bold text-foreground'>{axis.label}:</span> {axis.hint}</li>)}
                <li><span className='font-bold text-foreground'>امتیاز قدرت:</span> میانگین وزنی شاخص‌ها (دیده‌شدن ۳۵٪، رتبه ۲۵٪، حضور در ۳ رتبه اول ۱۵٪، پوشش مدل‌ها ۱۵٪، پوشش پرامپت‌ها ۱۰٪).</li>
              </ul>
            </details>
          </>
        )}
      </CardContent>
    </Card>
  )
}
