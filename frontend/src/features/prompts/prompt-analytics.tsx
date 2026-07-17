import { useState, useEffect, useCallback } from 'react'
import { format } from 'date-fns'
import { useNavigate, useParams } from '@tanstack/react-router'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { DatePicker } from '@/components/date-picker'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { toast } from 'sonner'
import { Loader2, RotateCcw, SlidersHorizontal } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { getPromptBrandTrends, getPromptRankings, listPrompts, getErrorMessage, type PromptBrandTrends, type PromptRankingItem, type PromptRead } from '@/lib/api'
import { BrandTrendChart } from './brand-trend-chart'

const RANK_BG = ['#ef4444', '#dc2626', '#b91c1c', '#f5f0e8', '#e0ddd5']

export function PromptAnalyticsPage() {
  const { projectId, promptId } = useParams({ from: '/_authenticated/projects_/$projectId/prompts/$promptId' })
  const navigate = useNavigate()
  const [prompt, setPrompt] = useState<PromptRead | null>(null)
  const [rankings, setRankings] = useState<PromptRankingItem[]>([])
  const [trends, setTrends] = useState<PromptBrandTrends | null>(null)
  const [allTrends, setAllTrends] = useState<PromptBrandTrends | null>(null)
  const [selectedModel, setSelectedModel] = useState('all')
  const [selectedBrand, setSelectedBrand] = useState('all')
  const [startDate, setStartDate] = useState<Date>()
  const [endDate, setEndDate] = useState<Date>()
  const [trendLoading, setTrendLoading] = useState(false)
  const [dateError, setDateError] = useState('')
  const [loading, setLoading] = useState(true)

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const [promptsData, rankingsData, trendData] = await Promise.all([listPrompts(Number(projectId)), getPromptRankings(Number(promptId)), getPromptBrandTrends(Number(promptId))])
      setPrompt(promptsData.find(p => p.id === Number(promptId)) || null)
      setRankings(rankingsData)
      setTrends(trendData)
      setAllTrends(trendData)
    }
    catch (e) { toast.error(getErrorMessage(e, 'خطا در دریافت آنالیز')) }
    finally { setLoading(false) }
  }, [projectId, promptId])

  useEffect(() => { fetchData() }, [fetchData])

  const applyTrendFilters = async () => {
    if (startDate && endDate && startDate > endDate) {
      setDateError('تاریخ شروع باید قبل از تاریخ پایان باشد.')
      return
    }
    setDateError('')
    setTrendLoading(true)
    try {
      const filtered = await getPromptBrandTrends(Number(promptId), {
        ai_model_id: selectedModel === 'all' ? undefined : Number(selectedModel),
        brand_ids: selectedBrand === 'all' ? undefined : [Number(selectedBrand)],
        start_date: startDate ? `${format(startDate, 'yyyy-MM-dd')}T00:00:00` : undefined,
        end_date: endDate ? `${format(endDate, 'yyyy-MM-dd')}T23:59:59` : undefined,
      })
      setTrends(filtered)
    } catch (e) { toast.error(getErrorMessage(e, 'خطا در فیلتر نمودار')) }
    finally { setTrendLoading(false) }
  }

  const clearTrendFilters = () => {
    setSelectedModel('all')
    setSelectedBrand('all')
    setStartDate(undefined)
    setEndDate(undefined)
    setDateError('')
    setTrends(allTrends)
  }

  const modelOptions = [...new Map((allTrends?.items ?? []).map(item => [item.ai_model_id, item.ai_model])).entries()]
  const brandOptions = [...new Map((allTrends?.items ?? []).map(item => [item.brand_id, item.brand])).entries()]
  const activeFilterCount = [selectedModel !== 'all', selectedBrand !== 'all', Boolean(startDate), Boolean(endDate)].filter(Boolean).length

  const groupedByModel = rankings.reduce<Record<string, PromptRankingItem[]>>((acc, item) => { if (!acc[item.ai_model]) acc[item.ai_model] = []; acc[item.ai_model].push(item); return acc }, {})

  if (loading) return (
    <div className="min-h-full bg-bg p-6 font-vazirmatn" dir="rtl">
      <Skeleton className="mb-4 h-8 w-48 bg-accent" />
      <Skeleton className="mb-4 h-24 w-full bg-accent" />
      <Skeleton className="h-64 w-full bg-accent" />
    </div>
  )

  return (
    <div className="min-h-full bg-bg font-vazirmatn" dir="rtl">
      <Header fixed className="bg-bg">
        <div className="flex items-center gap-3">
          <Button variant="outline" onClick={() => navigate({ to: '/projects/' + projectId })} className="border-border font-bold">
            ← بازگشت به پروژه
          </Button>
          <h1 className="text-lg font-black">آنالیز پرامپت</h1>
        </div>
      </Header>
      <Main>
        {prompt && (
          <Card className="mb-6 border-border shadow-[6px_6px_0_var(--color-shadow)]">
            <CardContent className="py-4">
              <p className="whitespace-pre-wrap text-sm font-medium leading-relaxed">{prompt.text}</p>
            </CardContent>
          </Card>
        )}

        {allTrends && allTrends.items.length > 0 && (
          <div className="mb-6 space-y-4">
            <Card className="border-border/70 bg-card/95 shadow-lg">
              <CardHeader className="gap-4 border-b border-border/70 pb-5">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="flex items-start gap-3">
                    <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                      <SlidersHorizontal className="size-5" aria-hidden="true" />
                    </div>
                    <div className="space-y-1">
                      <CardTitle className="text-base font-bold">فیلترهای نمودار</CardTitle>
                      <CardDescription className="text-sm font-medium text-muted-text">داده‌ی نمودار را بر اساس مدل، برند و بازه‌ی زمانی محدود کنید.</CardDescription>
                    </div>
                  </div>
                  <Badge variant="outline" className="w-fit shrink-0 border-border/70">
                    {activeFilterCount ? `${activeFilterCount.toLocaleString('fa-IR')} فیلتر فعال` : 'بدون فیلتر'}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-5 pt-5">
                <div className="grid gap-4 rounded-lg border border-border/70 bg-muted/20 p-4 md:grid-cols-2 lg:grid-cols-4">
                  <div className="grid gap-2">
                    <label className="text-sm font-semibold" htmlFor="trend-model">مدل AI</label>
                    <Select value={selectedModel} onValueChange={setSelectedModel}>
                      <SelectTrigger id="trend-model" className="h-11 border-border/80 bg-background font-medium"><SelectValue placeholder="همه مدل‌ها" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">همه مدل‌ها</SelectItem>
                        {modelOptions.map(([id, name]) => <SelectItem key={id} value={String(id)}>{name}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="grid gap-2">
                    <label className="text-sm font-semibold" htmlFor="trend-brand">برند</label>
                    <Select value={selectedBrand} onValueChange={setSelectedBrand}>
                      <SelectTrigger id="trend-brand" className="h-11 border-border/80 bg-background font-medium"><SelectValue placeholder="همه برندها" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">همه برندها</SelectItem>
                        {brandOptions.map(([id, name]) => <SelectItem key={id} value={String(id)}>{name}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="grid gap-2">
                    <span className="text-sm font-semibold">از تاریخ</span>
                    <DatePicker selected={startDate} onSelect={setStartDate} placeholder="انتخاب تاریخ شروع" />
                  </div>
                  <div className="grid gap-2">
                    <span className="text-sm font-semibold">تا تاریخ</span>
                    <DatePicker selected={endDate} onSelect={setEndDate} placeholder="انتخاب تاریخ پایان" />
                  </div>
                </div>
                {dateError && <p role="alert" className="text-sm font-medium text-destructive">{dateError}</p>}
                <div className="flex flex-col gap-3 border-t border-border/70 pt-4 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-xs text-muted-foreground">برای به‌روزرسانی نمودار، فیلترها را اعمال کنید.</p>
                  <div className="flex flex-wrap gap-2">
                  <Button type="button" onClick={applyTrendFilters} disabled={trendLoading} className="min-w-32 font-semibold">
                    {trendLoading && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
                    {trendLoading ? 'در حال بارگذاری...' : 'اعمال فیلتر'}
                  </Button>
                  <Button type="button" variant="outline" onClick={clearTrendFilters} disabled={trendLoading} className="font-semibold">
                    <RotateCcw className="size-4" aria-hidden="true" />
                    پاک کردن
                  </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
            {trends && trends.items.length > 0 ? <BrandTrendChart items={trends.items} /> : <Card className="border-border shadow-[6px_6px_0_var(--color-shadow)]"><CardContent className="py-10 text-center text-sm font-medium text-muted-text">برای این فیلتر داده‌ای پیدا نشد.</CardContent></Card>}
          </div>
        )}

        {rankings.length === 0 && (
          <Card className="border-border shadow-[6px_6px_0_var(--color-shadow)]">
            <CardContent className="py-8 text-center">
              <p className="text-sm font-medium text-muted-text">رتبه‌بندی برندها برای این پرامپت هنوز ثبت نشده است. ابتدا پرامپت را اجرا کنید.</p>
            </CardContent>
          </Card>
        )}

        {Object.entries(groupedByModel).map(([model, items]) => {
          const sorted = [...items].sort((a, b) => a.rank - b.rank)
          const maxRank = Math.max(...sorted.map(i => i.rank), 1)
          return (
            <Card key={model} className="mb-5 border-border shadow-[6px_6px_0_var(--color-shadow)]">
              <CardHeader>
                <CardTitle className="text-base font-black">{model}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {sorted.map((item, i) => {
                  const pct = Math.max(((maxRank - item.rank + 1) / maxRank) * 100, 10)
                  return (
                    <div key={item.brand + model} className="space-y-1">
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span
                            className="inline-flex size-7 items-center justify-center border-2 border-border text-xs font-black"
                            style={{ background: RANK_BG[i] || '#66625d', color: '#161616' }}
                          >
                            {item.rank}
                          </span>
                          <span className="text-sm font-bold">{item.brand}</span>
                        </div>
                        {item.domain && <span className="text-xs font-medium text-muted-text">{item.domain}</span>}
                      </div>
                      <div className="h-2.5 overflow-hidden border-2 border-border bg-[#eeeeee]">
                        <div className="h-full border-r-2 border-border bg-accent-neon transition-all duration-300" style={{ width: pct + '%' }} />
                      </div>
                    </div>
                  )
                })}
              </CardContent>
            </Card>
          )
        })}

        {rankings.length > 0 && Object.keys(groupedByModel).length === 0 && (
          <p className="text-sm font-medium text-muted-text">داده‌ای برای نمایش وجود ندارد.</p>
        )}
      </Main>
    </div>
  )
}
