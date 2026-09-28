import { useEffect, useState } from 'react'
import { Link, useNavigate } from '@tanstack/react-router'
import { FolderKanban, BarChart3, LogOut } from 'lucide-react'
import { useAuthStore } from '@/stores/auth-store'
import { getBrandRankSummary, getCurrentUser, listProjects, listPrompts, logout, type BrandRankSummaryItem, type ProjectRead, type PromptRead } from '@/lib/api'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'

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
  const [promptId, setPromptId] = useState('all')
  const [days, setDays] = useState<7 | 30>(7)
  const [result, setResult] = useState<{ key: string; items: BrandRankSummaryItem[]; error?: boolean } | null>(null)
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

  const requestKey = `${projectId}:${promptId}:${days}`
  useEffect(() => {
    if (!projectId) return
    getBrandRankSummary(Number(projectId), {
      days,
      prompt_id: promptId === 'all' ? undefined : Number(promptId),
      page: 1,
      page_size: 100,
    })
      .then(page => setResult({ key: requestKey, items: page.items }))
      .catch(() => setResult({ key: requestKey, items: [], error: true }))
  }, [projectId, promptId, days, requestKey])

  const current = result?.key === requestKey ? result : null

  return (
    <Card className='mt-6 border-border shadow-[6px_6px_0_var(--color-shadow)]'>
      <CardHeader className='gap-2'>
        <CardTitle className='text-lg font-black'>گزارش رتبه برندها</CardTitle>
        <CardDescription>میانگین رتبهٔ برندها در همهٔ مدل‌ها، طی ۷ یا ۳۰ روز گذشته؛ رتبهٔ کمتر بهتر است.</CardDescription>
      </CardHeader>
      <CardContent className='space-y-4'>
        <div className='grid gap-3 sm:grid-cols-2 lg:grid-cols-3'>
          <label className='grid gap-1.5 text-sm font-bold'>پروژه
            <Select value={projectId} onValueChange={value => { setProjectId(value); setPromptId('all') }} disabled={!projects.length}>
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
            <table className='w-full min-w-[640px] text-right text-sm'>
              <thead className='border-b-2 border-border bg-muted/30 text-muted-text'>
                <tr><th scope='col' className='p-2'>پرامپت</th><th scope='col' className='p-2'>برند</th><th scope='col' className='p-2'>میانگین رتبه</th><th scope='col' className='p-2'>تعداد مشاهده</th></tr>
              </thead>
              <tbody>
                {current.items.map((item, index) => <tr key={`${item.prompt_id}-${item.brand}-${index}`} className='border-b border-border/60 last:border-0'>
                  <td className='max-w-[360px] whitespace-normal p-2'>{item.prompt}</td>
                  <td className='p-2 font-bold'>{item.brand}{item.domain && <span className='ms-2 text-xs font-normal text-muted-text' dir='ltr'>{item.domain}</span>}</td>
                  <td className='p-2 font-black tabular-nums'>{item.average_rank.toFixed(2)}</td>
                  <td className='p-2 tabular-nums'>{item.observations.toLocaleString('fa-IR')}</td>
                </tr>)}
              </tbody>
            </table>
          </div>
        ) : <p className='py-6 text-center text-sm text-muted-text'>در این بازه برای پرامپت‌های انتخاب‌شده رتبه‌ای ثبت نشده است.</p>)}
      </CardContent>
    </Card>
  )
}
