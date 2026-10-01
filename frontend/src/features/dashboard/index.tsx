import { Fragment, useEffect, useState } from 'react'
import { Link, useNavigate } from '@tanstack/react-router'
import { Download, FolderKanban, BarChart3, LogOut, Printer } from 'lucide-react'
import { useAuthStore } from '@/stores/auth-store'
import { getBrandRankSummary, getCurrentUser, getPromptBrandTrends, listObservedBrands, listProjects, listPrompts, logout, type BrandRankSummaryItem, type BrandTrend, type ObservedBrand, type ProjectRead, type PromptRead } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { rankDetailsCsv, summarizeModelRanks, tehranBounds, tehranReportDays } from './rank-model-details'

export function DashboardPage() {
  const navigate = useNavigate()
  const { clearAuth, setUser, user } = useAuthStore()
  const firstName = user?.first_name || ''
  useEffect(() => {
    getCurrentUser().then(setUser).catch(() => {})
  }, [setUser])

  const handleLogout = () => { void logout().finally(() => { clearAuth(); navigate({ to: '/sign-in' }) }) }

  return (
    <div className="min-h-full bg-bg font-vazirmatn" dir="rtl">
      <Header fixed className="bg-bg">
        <h1 className="text-lg font-black">داشبورد</h1>
      </Header>
      <Main fixed>
        <div className="mb-8">
          <h1 className="text-3xl font-black tracking-tight sm:text-4xl lg:text-5xl">
            {firstName ? `سلام ${firstName}` : 'به FanoosAI خوش آمدی'}
          </h1>
          <p className="mt-2 max-w-prose text-base font-medium text-muted-text">
            سیستم مدیریت پرامپت و آنالیز برند. پروژه‌هات رو مدیریت کن، پرامپت بساز و رتبه برندها رو آنالیز کن.
          </p>
        </div>

        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          <Card className="relative border-border shadow-[6px_6px_0_var(--color-shadow)] transition-transform hover:-translate-x-0.5 hover:-translate-y-0.5">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-2xl"><FolderKanban className="size-6" /> مدیریت پروژه‌ها</CardTitle>
              <CardDescription className="text-sm font-medium text-muted-text">مشاهده، ایجاد و مدیریت پروژه‌ها و پرامپت‌ها</CardDescription>
            </CardHeader>
            <CardContent>
              <span className="font-bold text-foreground">مشاهده پروژه‌ها ←</span>
            </CardContent>
            <Link to='/projects' className="absolute inset-0 rounded-xl focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none">
              <span className="sr-only">مشاهده پروژه‌ها</span>
            </Link>
          </Card>

          <Card className="relative border-border shadow-[6px_6px_0_var(--color-shadow)] transition-transform hover:-translate-x-0.5 hover:-translate-y-0.5">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-2xl"><BarChart3 className="size-6" /> آنالیز برند</CardTitle>
              <CardDescription className="text-sm font-medium text-muted-text">مشاهده و تحلیل رتبه برندها در پرامپت‌ها</CardDescription>
            </CardHeader>
            <CardContent>
              <span className="font-bold text-foreground">مشاهده آنالیتیکس ←</span>
            </CardContent>
            <Link to='/analytics' className="absolute inset-0 rounded-xl focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none">
              <span className="sr-only">مشاهده آنالیتیکس</span>
            </Link>
          </Card>

          <Card className="relative border-border shadow-[6px_6px_0_var(--color-shadow)] transition-transform hover:-translate-x-0.5 hover:-translate-y-0.5">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-2xl"><LogOut className="size-6" /> خروج</CardTitle>
              <CardDescription className="text-sm font-medium text-muted-text">خروج از حساب کاربری</CardDescription>
            </CardHeader>
            <CardContent>
              <span className="font-bold text-foreground">خروج ←</span>
            </CardContent>
            <button type='button' onClick={handleLogout} className="absolute inset-0 rounded-xl focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none">
              <span className="sr-only">خروج از حساب</span>
            </button>
          </Card>
        </div>
        <BrandRankReport />
      </Main>
    </div>
  )
}

function BrandRankReport() {
  const [projects, setProjects] = useState<ProjectRead[]>([])
  const [projectId, setProjectId] = useState('')
  const [prompts, setPrompts] = useState<PromptRead[]>([])
  const [brands, setBrands] = useState<ObservedBrand[]>([])
  const [promptId, setPromptId] = useState('all')
  const [brandId, setBrandId] = useState('all')
  const [days, setDays] = useState<7 | 30>(7)
  const [result, setResult] = useState<{ key: string; items: BrandRankSummaryItem[]; error?: boolean } | null>(null)
  const [expandedKey, setExpandedKey] = useState('')
  const [trendResult, setTrendResult] = useState<{ key: string; items: BrandTrend[]; error?: boolean } | null>(null)
  const [projectsLoaded, setProjectsLoaded] = useState(false)

  useEffect(() => {
    listProjects()
      .then(items => {
        setProjects(items)
        if (items.length) setProjectId(String(items[0].id))
      })
      .catch(() => setProjectsLoaded(true))
      .finally(() => setProjectsLoaded(true))
  }, [])

  useEffect(() => {
    if (projectId) listPrompts(Number(projectId)).then(setPrompts).catch(() => setPrompts([]))
  }, [projectId])

  useEffect(() => {
    if (projectId) listObservedBrands(Number(projectId)).then(setBrands).catch(() => setBrands([]))
  }, [projectId])

  const requestKey = `${projectId}:${promptId}:${brandId}:${days}`
  useEffect(() => {
    if (!projectId) return
    getBrandRankSummary(Number(projectId), {
      days,
      prompt_id: promptId === 'all' ? undefined : Number(promptId),
      brand_id: brandId === 'all' ? undefined : Number(brandId),
      page: 1,
      page_size: 100,
    })
      .then(page => setResult({ key: requestKey, items: page.items }))
      .catch(() => setResult({ key: requestKey, items: [], error: true }))
  }, [projectId, promptId, brandId, days, requestKey])

  const current = result?.key === requestKey ? result : null
  const dayKeys = tehranReportDays(days)

  const toggleDetails = (item: BrandRankSummaryItem) => {
    const key = `${requestKey}:${item.prompt_id}:${item.brand_id}`
    if (expandedKey === key) {
      setExpandedKey('')
      return
    }
    setExpandedKey(key)
    const bounds = tehranBounds(dayKeys)
    getPromptBrandTrends(item.prompt_id, {
      brand_ids: [item.brand_id],
      start_date: bounds.start_date,
      end_date: bounds.end_date,
    })
      .then(trends => setTrendResult({ key, items: trends.items }))
      .catch(() => setTrendResult({ key, items: [], error: true }))
  }

  const downloadCsv = (item: BrandRankSummaryItem, details: ReturnType<typeof summarizeModelRanks>) => {
    const csv = rankDetailsCsv(details, dayKeys)
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
    const link = document.createElement('a')
    link.href = url
    link.download = `brand-ranks-${item.prompt_id}-${item.brand_id}-${days}d.csv`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  }

  const printPdf = () => {
    const className = 'printing-brand-rank-details'
    const cleanup = () => document.body.classList.remove(className)
    document.body.classList.add(className)
    window.addEventListener('afterprint', cleanup, { once: true })
    window.print()
  }

  return (
    <Card className='brand-rank-report-card mt-6 border-border shadow-[6px_6px_0_var(--color-shadow)]'>
      <CardHeader className='gap-2'>
        <CardTitle className='text-lg font-black'>گزارش رتبه برندها</CardTitle>
        <CardDescription>میانگین رتبهٔ برندها در همهٔ مدل‌ها، طی ۷ یا ۳۰ روز گذشته؛ رتبهٔ کمتر بهتر است.</CardDescription>
      </CardHeader>
      <CardContent className='space-y-4'>
        <div className='brand-rank-filters grid gap-3 sm:grid-cols-2 xl:grid-cols-4'>
          <label className='grid gap-1.5 text-sm font-bold'>پروژه
            <Select value={projectId} onValueChange={value => { setProjectId(value); setPromptId('all'); setBrandId('all') }} disabled={!projects.length}>
              <SelectTrigger className='border-border bg-background'><SelectValue placeholder='انتخاب پروژه' /></SelectTrigger>
              <SelectContent>{projects.map(project => <SelectItem key={project.id} value={String(project.id)}>{project.name}</SelectItem>)}</SelectContent>
            </Select>
          </label>
          <label className='grid gap-1.5 text-sm font-bold'>پرامپت
            <Select value={promptId} onValueChange={setPromptId} disabled={!projectId}>
              <SelectTrigger className='border-border bg-background'><SelectValue placeholder='همهٔ پرامپت‌ها' /></SelectTrigger>
              <SelectContent>
                <SelectItem value='all'>همهٔ پرامپت‌ها</SelectItem>
                {prompts.map(prompt => <SelectItem key={prompt.id} value={String(prompt.id)}>{prompt.text.slice(0, 65)}{prompt.text.length > 65 ? '...' : ''}</SelectItem>)}
              </SelectContent>
            </Select>
          </label>
          <label className='grid gap-1.5 text-sm font-bold'>برند
            <Select value={brandId} onValueChange={setBrandId} disabled={!projectId}>
              <SelectTrigger className='border-border bg-background'><SelectValue placeholder='همهٔ برندها' /></SelectTrigger>
              <SelectContent>
                <SelectItem value='all'>همهٔ برندها</SelectItem>
                {brands.map(brand => <SelectItem key={brand.brand_id} value={String(brand.brand_id)}>{brand.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </label>
          <label className='grid gap-1.5 text-sm font-bold'>بازه
            <Select value={String(days)} onValueChange={value => setDays(Number(value) as 7 | 30)}>
              <SelectTrigger className='border-border bg-background'><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value='7'>۷ روز گذشته</SelectItem>
                <SelectItem value='30'>۳۰ روز گذشته</SelectItem>
              </SelectContent>
            </Select>
          </label>
        </div>
        {!projectsLoaded && <Skeleton className='h-24 w-full bg-accent' />}
        {projectsLoaded && !projectId && <p className='py-6 text-center text-sm text-muted-text'>برای نمایش گزارش ابتدا پروژه بساز.</p>}
        {current?.error && <p role='alert' className='text-sm font-bold text-red-600'>دریافت گزارش رتبه‌ها ممکن نشد.</p>}
        {projectId && !current && <Skeleton className='h-32 w-full bg-accent' />}
        {current && !current.error && (current.items.length ? (
          <div className='overflow-x-auto border border-border/70'>
            <table className='rank-summary-table w-full min-w-[640px] text-right text-sm'>
              <thead className='border-b-2 border-border bg-muted/30 text-muted-text'>
                <tr><th scope='col' className='p-2'>پرامپت</th><th scope='col' className='p-2'>برند</th><th scope='col' className='p-2'>میانگین رتبه</th><th scope='col' className='p-2'>تعداد مشاهده</th></tr>
              </thead>
              <tbody>
                {current.items.map((item, index) => {
                  const detailKey = `${requestKey}:${item.prompt_id}:${item.brand_id}`
                  const isExpanded = expandedKey === detailKey
                  const details = trendResult?.key === detailKey ? summarizeModelRanks(trendResult.items, dayKeys) : []
                  return <Fragment key={`${item.prompt_id}-${item.brand_id}-${index}`}>
                    <tr className='border-b border-border/60 last:border-0'>
                      <td className='max-w-[360px] whitespace-normal p-2'>
                        <button type='button' aria-expanded={isExpanded} onClick={() => toggleDetails(item)} className='text-right font-medium underline decoration-dotted underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'>
                          {item.prompt}
                        </button>
                      </td>
                      <td className='p-2 font-bold'>{item.brand}{item.domain && <span className='ms-2 text-xs font-normal text-muted-text' dir='ltr'>{item.domain}</span>}</td>
                      <td className='p-2 font-black tabular-nums'>{item.average_rank.toFixed(2)}</td>
                      <td className='p-2 tabular-nums'>{item.observations.toLocaleString('fa-IR')}</td>
                    </tr>
                    {isExpanded && <tr key={`${detailKey}-details`} className='brand-rank-details-row border-b-2 border-border bg-muted/10'>
                      <td colSpan={4} className='p-3'>
                        <div className='brand-rank-print-heading hidden pb-3 text-sm font-bold print:block'>
                          گزارش رتبهٔ روزانه: {item.prompt} — {item.brand} ({item.domain}) — بازهٔ {days} روزه
                        </div>
                        {trendResult?.key !== detailKey ? <Skeleton className='h-20 w-full bg-accent' /> : trendResult.error ? <p role='alert' className='py-3 text-sm font-bold text-red-600'>دریافت جزئیات مدل‌ها ممکن نشد.</p> : details.length === 0 ? <p className='py-3 text-sm text-muted-text'>برای این برند جزئیاتی در این بازه نیست.</p> : (
                          <>
                            <div className='brand-rank-details-actions no-print mb-3 flex justify-end gap-2'>
                              <Button type='button' variant='outline' size='sm' onClick={() => downloadCsv(item, details)}><Download className='me-2 size-4' aria-hidden='true' />دریافت CSV</Button>
                              <Button type='button' variant='outline' size='sm' onClick={printPdf}><Printer className='me-2 size-4' aria-hidden='true' />دریافت PDF</Button>
                            </div>
                            <div className='rank-model-details-scroll overflow-x-auto border border-border/70 bg-card'>
                            <table className='rank-model-details-table w-full min-w-[760px] text-right text-xs'>
                              <thead className='border-b border-border bg-muted/30 text-muted-text'><tr>
                                <th className='p-2'>مدل</th><th className='p-2'>میانگین رتبه</th><th className='p-2'>آخرین رتبه</th><th className='p-2'>تغییر</th><th className='p-2'>مشاهده روزانه</th>
                                {dayKeys.map(day => <th key={day} className='p-2'>{day.replace(/-/g, '/')}</th>)}
                              </tr></thead>
                              <tbody>{details.map(detail => <tr key={detail.ai_model_id} className='border-b border-border/50 last:border-0'>
                                <td className='p-2 font-bold' dir='ltr'>{detail.ai_model}</td>
                                <td className='p-2 font-bold tabular-nums'>{detail.average_rank?.toFixed(2) ?? '—'}</td>
                                <td className='p-2 tabular-nums'>{detail.latest_rank ?? '—'}</td>
                                <td className={`p-2 font-bold tabular-nums ${detail.rank_change == null ? 'text-muted-text' : detail.rank_change <= 0 ? 'text-emerald-600' : 'text-red-600'}`}>{detail.rank_change == null ? '—' : `${detail.rank_change > 0 ? '+' : ''}${detail.rank_change}`}</td>
                                <td className='p-2 tabular-nums'>{detail.observations.toLocaleString('fa-IR')}</td>
                                {dayKeys.map(day => <td key={day} className='p-2 text-center tabular-nums'>{detail.daily[day] ?? '—'}</td>)}
                              </tr>)}</tbody>
                             </table>
                           </div>
                           </>
                         )}
                       </td>
                    </tr>}
                  </Fragment>
                })}
              </tbody>
            </table>
          </div>
        ) : <p className='py-6 text-center text-sm text-muted-text'>در این بازه برای پرامپت‌های انتخاب‌شده رتبه‌ای ثبت نشده است.</p>)}
      </CardContent>
    </Card>
  )
}
