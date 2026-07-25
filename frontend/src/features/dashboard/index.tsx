import { useEffect, useState } from 'react'
import { Link, useNavigate } from '@tanstack/react-router'
import { FolderKanban, BarChart3, LogOut } from 'lucide-react'
import { useAuthStore } from '@/stores/auth-store'
import { logout, getCurrentUser, listAdminModels, setModelActive, type AIModelRead } from '@/lib/api'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'

export function DashboardPage() {
  const navigate = useNavigate()
  const { clearAuth, setUser, user } = useAuthStore()
  const firstName = user?.first_name || ''
  const [models, setModels] = useState<AIModelRead[]>([])

  useEffect(() => {
    getCurrentUser().then(setUser).catch(() => {})
  }, [setUser])
  useEffect(() => { if (user?.is_superuser) listAdminModels().then(setModels).catch(() => {}) }, [user?.is_superuser])

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
        {user?.is_superuser && <Card className="mt-6 border-border"><CardHeader><CardTitle>مدیریت مدل‌ها</CardTitle></CardHeader><CardContent className="space-y-2">{models.map(model => <div key={model.id} className="flex justify-between"><span>{model.name}</span><button onClick={() => setModelActive(model.id, !model.is_active).then(updated => setModels(items => items.map(item => item.id === updated.id ? updated : item)))}>{model.is_active ? 'غیرفعال' : 'فعال'}</button></div>)}</CardContent></Card>}
      </Main>
    </div>
  )
}
