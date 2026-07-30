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
import { ExternalLink, FileText, Link2, Loader2, RotateCcw, SlidersHorizontal } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { Badge } from '@/components/ui/badge'
import { getProjectReferences, getPromptBrandTrends, getLatestRankings, getPromptHistory, listPrompts, getErrorMessage, type ProjectReference, type PromptBrandTrends, type PromptRankingItem, type PromptHistoryItem, type PromptRead } from '@/lib/api'
import { BrandTrendChart } from './brand-trend-chart'

const RANK_BG = ['#ef4444', '#dc2626', '#b91c1c', '#f5f0e8', '#e0ddd5']

export function modelResponseText(responseText: string | null): string {
  if (!responseText) return 'برای این اجرا پاسخی ثبت نشده است.'
  try {
    const payload = JSON.parse(responseText)
    const openAIText = payload?.choices?.[0]?.message?.content
    if (typeof openAIText === 'string') return openAIText
    const geminiText = payload?.candidates?.[0]?.content?.parts?.map((part: { text?: unknown } | null) => part?.text).filter((text: unknown) => typeof text === 'string').join('')
    if (geminiText) return geminiText
    const claudeText = Array.isArray(payload?.content)
      ? payload.content.filter((part: { type?: unknown; text?: unknown } | null) => part?.type === 'text' && typeof part.text === 'string').map((part: { text?: unknown }) => part.text as string).join('')
      : ''
    if (claudeText) return claudeText
  } catch { /* Older plain-text responses need no conversion. */ }
  return responseText
}

export function defaultTrendSelection(trends: PromptBrandTrends) {
  const modelId = trends.items[0]?.ai_model_id
  return {
    modelId: modelId ? String(modelId) : '',
    trends: {
      ...trends,
      items: modelId ? trends.items.filter(item => item.ai_model_id === modelId) : [],
    },
  }
}

export function PromptAnalyticsPage() {
  const { projectId, promptId } = useParams({ from: '/_authenticated/projects_/$projectId/prompts/$promptId' })
  const navigate = useNavigate()
  const [prompt, setPrompt] = useState<PromptRead | null>(null)
  const [rankings, setRankings] = useState<PromptRankingItem[]>([])
  const [trends, setTrends] = useState<PromptBrandTrends | null>(null)
  const [allTrends, setAllTrends] = useState<PromptBrandTrends | null>(null)
  const [selectedModel, setSelectedModel] = useState('')
  const [selectedBrand, setSelectedBrand] = useState('all')
  const [startDate, setStartDate] = useState<Date>()
  const [endDate, setEndDate] = useState<Date>()
  const [trendLoading, setTrendLoading] = useState(false)
  const [dateError, setDateError] = useState('')
  const [loading, setLoading] = useState(true)
  const [references, setReferences] = useState<ProjectReference[]>([])
  const [referencePage, setReferencePage] = useState(1)
  const [referenceTotal, setReferenceTotal] = useState(0)
  const [referenceLoading, setReferenceLoading] = useState(false)
  const [history, setHistory] = useState<PromptHistoryItem[]>([])
  const [historyModel, setHistoryModel] = useState('all')
  const [historyDate, setHistoryDate] = useState<Date>()
  const [historyLoading, setHistoryLoading] = useState(false)
  const [rankingPage, setRankingPage] = useState(1)
  const [rankingTotal, setRankingTotal] = useState(0)

  const fetchData = useCallback(async () => {
    try {
      const [promptsData, rankingsData, trendData, referenceData] = await Promise.all([
        listPrompts(Number(projectId)),
        getLatestRankings(Number(promptId)),
        getPromptBrandTrends(Number(promptId)),
        getProjectReferences(Number(projectId), { prompt_id: Number(promptId) }),
      ])
      const initialTrend = defaultTrendSelection(trendData)
      setPrompt(promptsData.find(p => p.id === Number(promptId)) || null)
      setRankings(rankingsData.items); setRankingTotal(rankingsData.total)
      setSelectedModel(initialTrend.modelId)
      setTrends(initialTrend.trends)
      setAllTrends(trendData)
      setReferences(referenceData.items)
      setReferenceTotal(referenceData.total)
    }
    catch (e) { toast.error(getErrorMessage(e, 'خطا در دریافت آنالیز')) }
    finally { setLoading(false) }
  }, [projectId, promptId])

  useEffect(() => { void Promise.resolve().then(fetchData) }, [fetchData])

  const loadProjectReferences = async (page = 1) => {
    setReferenceLoading(true)
    try {
      const result = await getProjectReferences(Number(projectId), {
        prompt_id: Number(promptId),
        page,
      })
      setReferences(result.items)
      setReferencePage(result.page)
      setReferenceTotal(result.total)
    } catch (e) { toast.error(getErrorMessage(e, 'خطا در دریافت منابع وب')) }
    finally { setReferenceLoading(false) }
  }

  const applyTrendFilters = async () => {
    if (startDate && endDate && startDate > endDate) {
      setDateError('تاریخ شروع باید قبل از تاریخ پایان باشد.')
      return
    }
    setDateError('')
    setTrendLoading(true)
    try {
      const filtered = await getPromptBrandTrends(Number(promptId), {
        ai_model_id: Number(selectedModel),
        brand_ids: selectedBrand === 'all' ? undefined : [Number(selectedBrand)],
        start_date: startDate ? `${format(startDate, 'yyyy-MM-dd')}T00:00:00` : undefined,
        end_date: endDate ? `${format(endDate, 'yyyy-MM-dd')}T23:59:59` : undefined,
      })
      setTrends(filtered)
      const ranked = await getLatestRankings(Number(promptId), { page: 1, ai_model_id: Number(selectedModel), brand_id: selectedBrand === 'all' ? undefined : Number(selectedBrand) })
      setRankings(ranked.items); setRankingTotal(ranked.total); setRankingPage(1)
      const query = new URLSearchParams()
      query.set('model', selectedModel)
      if (selectedBrand !== 'all') query.set('brand', selectedBrand)
      if (startDate) query.set('start', format(startDate, 'yyyy-MM-dd'))
      if (endDate) query.set('end', format(endDate, 'yyyy-MM-dd'))
      window.history.replaceState(null, '', `${window.location.pathname}?${query}`)
    } catch (e) { toast.error(getErrorMessage(e, 'خطا در فیلتر نمودار')) }
    finally { setTrendLoading(false) }
  }

  const clearTrendFilters = () => {
    if (!allTrends) return
    const initialTrend = defaultTrendSelection(allTrends)
    setSelectedModel(initialTrend.modelId)
    setSelectedBrand('all')
    setStartDate(undefined)
    setEndDate(undefined)
    setDateError('')
    setTrends(initialTrend.trends)
    window.history.replaceState(null, '', window.location.pathname)
  }

  const loadPromptHistory = async () => {
    setHistoryLoading(true)
    try {
      const date = historyDate ? format(historyDate, 'yyyy-MM-dd') : undefined
      const result = await getPromptHistory(Number(promptId), {
        ai_model_id: historyModel === 'all' ? undefined : Number(historyModel),
        start_date: date ? `${date}T00:00:00` : undefined,
        end_date: date ? `${date}T23:59:59` : undefined,
      })
      setHistory(result.items)
    } catch (e) { toast.error(getErrorMessage(e, 'خطا در دریافت متن خام پرامپت')) }
    finally { setHistoryLoading(false) }
  }

  const modelOptions = [...new Map((allTrends?.items ?? []).map(item => [item.ai_model_id, item.ai_model])).entries()]
  const brandOptions = [...new Map((allTrends?.items ?? []).map(item => [item.brand_id, item.brand])).entries()]
  const activeFilterCount = [Boolean(selectedModel), selectedBrand !== 'all', Boolean(startDate), Boolean(endDate)].filter(Boolean).length

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
                <div className="grid grid-cols-1 gap-4 rounded-lg border border-border/70 bg-muted/20 p-4 sm:grid-cols-2 2xl:grid-cols-4">
                  <div className="grid min-w-0 gap-2">
                    <label className="text-sm font-semibold" htmlFor="trend-model">مدل AI</label>
                    <Select value={selectedModel} onValueChange={setSelectedModel}>
                      <SelectTrigger id="trend-model" className="h-11 w-full min-w-0 border-border/80 bg-background font-medium"><SelectValue placeholder="انتخاب مدل" /></SelectTrigger>
                      <SelectContent>
                        {modelOptions.map(([id, name]) => <SelectItem key={id} value={String(id)}>{name}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="grid min-w-0 gap-2">
                    <label className="text-sm font-semibold" htmlFor="trend-brand">برند</label>
                    <Select value={selectedBrand} onValueChange={setSelectedBrand}>
                      <SelectTrigger id="trend-brand" className="h-11 w-full min-w-0 border-border/80 bg-background font-medium"><SelectValue placeholder="همه برندها" /></SelectTrigger>
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

        <Card className="mb-6 border-border shadow-[6px_6px_0_var(--color-shadow)]">
          <CardHeader className="gap-3 border-b border-border/70">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="flex items-start gap-3">
                <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Link2 className="size-5" aria-hidden="true" />
                </div>
                <div>
                  <CardTitle className="text-base font-bold">منابع وب این پرامپت</CardTitle>
                  <CardDescription className="mt-1 text-sm font-medium text-muted-text">رفرنس‌های ثبت‌شده برای این پرامپت.</CardDescription>
                </div>
              </div>
              <Badge variant="outline">{referenceTotal.toLocaleString('fa-IR')} منبع</Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4 pt-5">
            {references.length ? (
              <ol className="max-h-96 space-y-3 overflow-auto" aria-label="فهرست منابع وب">
                {references.map(reference => (
                  <li key={`${reference.prompt_id}-${reference.ai_model_id}-${reference.url}`} className="border border-border bg-background p-3">
                    <a className="inline-flex max-w-full items-start gap-1 break-all text-sm font-semibold text-primary underline underline-offset-4" href={reference.url} target="_blank" rel="noreferrer" dir="ltr">
                      <span>{reference.url}</span>
                      <ExternalLink className="mt-1 size-3.5 shrink-0" aria-hidden="true" />
                      <span className="sr-only">در پنجره جدید باز می‌شود</span>
                    </a>
                    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-text">
                      <span className="max-w-full truncate">پرامپت {reference.prompt_id.toLocaleString('fa-IR')}: {reference.prompt}</span>
                      <span>{reference.ai_model}</span>
                      <time dateTime={reference.run_date}>{new Date(reference.run_date).toLocaleString('fa-IR')}</time>
                    </div>
                  </li>
                ))}
              </ol>
            ) : (
              <p role="status" className="py-6 text-center text-sm font-medium text-muted-text">برای فیلتر انتخاب‌شده منبعی ثبت نشده است.</p>
            )}
            {referenceTotal > 50 && (
              <div className="flex items-center justify-end gap-2 border-t border-border/70 pt-4">
                <Button type="button" variant="outline" disabled={referenceLoading || referencePage === 1} onClick={() => loadProjectReferences(referencePage - 1)}>قبلی</Button>
                <span className="text-xs text-muted-text">صفحه {referencePage.toLocaleString('fa-IR')}</span>
                <Button type="button" variant="outline" disabled={referenceLoading || referencePage * 50 >= referenceTotal} onClick={() => loadProjectReferences(referencePage + 1)}>بعدی</Button>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="mb-6 border-border shadow-[6px_6px_0_var(--color-shadow)]">
          <CardHeader className="gap-2 border-b border-border/70">
            <div className="flex items-start gap-3">
              <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <FileText className="size-5" aria-hidden="true" />
              </div>
              <div>
                <CardTitle className="text-base font-bold">پاسخ مدل</CardTitle>
                <CardDescription className="mt-1 text-sm font-medium text-muted-text">مدل و تاریخ اجرا را انتخاب کنید تا پاسخ دریافت‌شده از مدل را ببینید.</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4 pt-5">
            <div className="grid gap-4 rounded-lg border border-border/70 bg-muted/20 p-4 md:grid-cols-[1fr_1fr_auto] md:items-end">
              <div className="grid gap-2">
                <label className="text-sm font-semibold" htmlFor="raw-prompt-model">مدل AI</label>
                <Select value={historyModel} onValueChange={setHistoryModel}>
                  <SelectTrigger id="raw-prompt-model" className="h-11 border-border/80 bg-background font-medium"><SelectValue placeholder="همه مدل‌ها" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">همه مدل‌ها</SelectItem>
                    {prompt?.models.map(model => <SelectItem key={model.id} value={String(model.id)}>{model.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <span className="text-sm font-semibold">تاریخ اجرا</span>
                <DatePicker selected={historyDate} onSelect={setHistoryDate} placeholder="همه تاریخ‌ها" />
              </div>
              <Button type="button" onClick={loadPromptHistory} disabled={historyLoading} className="h-11 font-semibold">
                {historyLoading && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
                نمایش پاسخ
              </Button>
            </div>
            {history.length > 0 ? (
              <div className="space-y-4">
                {history.map(run => (
                  <div key={run.ai_run_id} className="border-2 border-border bg-background">
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b-2 border-border bg-muted/30 px-4 py-3 text-xs font-bold">
                      <span>{run.ai_model}</span>
                      <span>{new Date(run.run_date).toLocaleString('fa-IR')}</span>
                    </div>
                    <div className="max-h-80 overflow-auto break-words p-4 text-sm leading-7 [&_a]:underline [&_h1]:mb-4 [&_h1]:text-xl [&_h1]:font-black [&_h2]:mb-3 [&_h2]:text-lg [&_h2]:font-black [&_h3]:mb-2 [&_h3]:font-bold [&_hr]:my-4 [&_li]:ms-5 [&_ol]:my-3 [&_ol]:list-decimal [&_p]:my-3 [&_strong]:font-black [&_ul]:my-3 [&_ul]:list-disc" dir="auto"><ReactMarkdown>{modelResponseText(run.response_text)}</ReactMarkdown></div>
                  </div>
                ))}
              </div>
            ) : (
              <p role="status" className="py-5 text-center text-sm font-medium text-muted-text">برای فیلتر انتخاب‌شده اجرایی پیدا نشد.</p>
            )}
          </CardContent>
        </Card>

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
        {rankingTotal > 20 && <div className="mb-5 flex gap-2"><Button variant="outline" disabled={rankingPage === 1} onClick={async () => { const page = rankingPage - 1; const result = await getLatestRankings(Number(promptId), { page }); setRankings(result.items); setRankingPage(page) }}>قبلی</Button><Button variant="outline" disabled={rankingPage * 20 >= rankingTotal} onClick={async () => { const page = rankingPage + 1; const result = await getLatestRankings(Number(promptId), { page }); setRankings(result.items); setRankingPage(page) }}>بعدی</Button></div>}
      </Main>
    </div>
  )
}
