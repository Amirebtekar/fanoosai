import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import type { BrandTrend } from '@/lib/api'
import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

const COLORS = ['#60a5fa', '#34d399', '#fbbf24', '#c084fc', '#22d3ee', '#fb7185']
const MAX_VISIBLE_SERIES = 6

function trendMeta(trend: BrandTrend['trend']) {
  if (trend === 'up') return { label: 'بهبود', icon: ArrowUpRight, className: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300' }
  if (trend === 'down') return { label: 'افت', icon: ArrowDownRight, className: 'border-red-400/30 bg-red-400/10 text-red-300' }
  return { label: 'ثابت', icon: Minus, className: 'border-border bg-muted text-muted-foreground' }
}

export function BrandTrendChart({ items }: { items: BrandTrend[] }) {
  const visibleItems = items.slice(0, MAX_VISIBLE_SERIES)
  const hiddenCount = Math.max(items.length - visibleItems.length, 0)
  const rows = new Map<string, Record<string, string | number>>()
  const series = visibleItems.map((item, index) => ({
    ...item,
    key: `brand_${index}`,
    color: COLORS[index % COLORS.length],
  }))

  for (const item of series) {
    for (const point of item.points) {
      const row = rows.get(point.date) ?? { date: point.date }
      row[item.key] = point.rank
      rows.set(point.date, row)
    }
  }

  const maxRank = Math.max(...visibleItems.flatMap((item) => item.points.map((point) => point.rank)), 1)
  const formatDate = (value: string) => new Intl.DateTimeFormat('fa-IR', { month: 'short', day: 'numeric' }).format(new Date(value))

  return (
    <Card className='overflow-hidden'>
      <CardHeader className='gap-3 border-b border-border/70 pb-5'>
        <div className='flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between'>
          <div className='space-y-1'>
            <CardTitle className='text-base'>روند رتبه برندها</CardTitle>
            <CardDescription>رتبه‌ی کمتر بهتر است؛ برای خوانایی، حداکثر ۶ برند هم‌زمان نمایش داده می‌شود.</CardDescription>
          </div>
          <Badge variant='outline' className='w-fit shrink-0'>
            {items.length.toLocaleString('fa-IR')} سری داده
          </Badge>
        </div>
      </CardHeader>
      <CardContent className='space-y-6 pt-6'>
        <div className='h-[330px] w-full min-w-0' role='img' aria-label='نمودار روند رتبه برندها در طول زمان' dir='ltr'>
          <ResponsiveContainer width='100%' height='100%'>
            <LineChart data={[...rows.values()]} margin={{ top: 8, right: 12, left: -12, bottom: 8 }}>
              <CartesianGrid stroke='var(--border)' strokeDasharray='3 5' opacity={0.55} />
              <XAxis dataKey='date' tickFormatter={formatDate} tick={{ fill: 'var(--muted-foreground)', fontSize: 11 }} axisLine={{ stroke: 'var(--border)' }} tickLine={false} minTickGap={28} />
              <YAxis reversed domain={[1, maxRank]} allowDecimals={false} tick={{ fill: 'var(--muted-foreground)', fontSize: 11 }} axisLine={false} tickLine={false} width={34} />
              <Tooltip
                cursor={{ stroke: 'var(--primary)', strokeDasharray: '4 4' }}
                labelFormatter={(value) => formatDate(String(value))}
                contentStyle={{ background: 'var(--popover)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', color: 'var(--popover-foreground)', direction: 'rtl' }}
                labelStyle={{ color: 'var(--muted-foreground)', marginBottom: 6 }}
                formatter={(value, name) => [`رتبه ${value}`, name]}
              />
              {series.map((item) => (
                <Line key={item.key} type='monotone' dataKey={item.key} name={item.brand} stroke={item.color} strokeWidth={2.5} dot={{ r: 3, strokeWidth: 1.5, fill: item.color }} activeDot={{ r: 6, strokeWidth: 2 }} connectNulls />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className='grid gap-2 sm:grid-cols-2 lg:grid-cols-3'>
          {series.map((item) => {
            const meta = trendMeta(item.trend)
            const TrendIcon = meta.icon
            return (
              <div key={item.key} className='flex min-w-0 items-center gap-3 rounded-lg border border-border/70 bg-muted/40 px-3 py-2.5'>
                <span aria-hidden='true' className='size-2.5 shrink-0 rounded-full' style={{ backgroundColor: item.color }} />
                <div className='min-w-0 flex-1'>
                  <p className='truncate text-sm font-medium' title={item.brand}>{item.brand}</p>
                  <p className='truncate text-xs text-muted-foreground' title={item.ai_model}>{item.ai_model}</p>
                </div>
                <Badge variant='outline' className={meta.className}>
                  <TrendIcon className='size-3.5' aria-hidden='true' />
                  {meta.label}
                </Badge>
              </div>
            )
          })}
        </div>
        {hiddenCount > 0 && <p className='text-xs text-muted-foreground'>+ {hiddenCount.toLocaleString('fa-IR')} سری دیگر در داده وجود دارد؛ برای مشاهده‌ی آن‌ها از فیلتر برند استفاده کنید.</p>}
      </CardContent>
    </Card>
  )
}
