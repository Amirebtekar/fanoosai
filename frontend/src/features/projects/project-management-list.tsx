import { useEffect, useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { getErrorMessage, listProjects, type ProjectRead } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { toast } from 'sonner'

export function ProjectManagementListPage() {
  const navigate = useNavigate()
  const [projects, setProjects] = useState<ProjectRead[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listProjects()
      .then(setProjects)
      .catch((e) => toast.error(getErrorMessage(e, 'دریافت پروژه‌ها ممکن نشد')))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="min-h-full bg-bg font-vazirmatn" dir="rtl">
      <Header fixed className="bg-bg"><h1 className="text-lg font-black">مدیریت پروژه‌ها</h1></Header>
      <Main fixed>
        <section className="mb-8 border-r-4 border-primary bg-card p-4" aria-labelledby="project-management-help">
          <div className="flex items-center gap-2">
            <h2 id="project-management-help" className="font-black">این صفحه برای چیست؟</h2>
            <Tooltip>
              <TooltipTrigger asChild><Button variant="ghost" size="sm">راهنما</Button></TooltipTrigger>
              <TooltipContent side="bottom">پروژه را انتخاب کنید تا تنظیمات، برندها، هشدارها و گزارش‌های آن را مدیریت کنید.</TooltipContent>
            </Tooltip>
          </div>
          <p className="mt-2 text-sm leading-6 text-muted-text">برای هر پروژه یک فضای مدیریت جدا وجود دارد؛ ابتدا پروژه را انتخاب کنید.</p>
        </section>

        {loading ? <div className="space-y-4">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-24 w-full bg-accent" />)}</div> : (
          <div className="space-y-4">
            {projects.map(project => <Card key={project.id} className="border-border shadow-[6px_6px_0_var(--color-shadow)]"><CardHeader className="flex-row items-center justify-between gap-4"><div><h2 className="font-black">{project.name}</h2>{project.description && <p className="mt-2 text-sm text-muted-text">{project.description}</p>}</div><Button variant="outline" onClick={() => navigate({ to: '/projects/' + project.id + '/manage' })}>مدیریت</Button></CardHeader></Card>)}
            {projects.length === 0 && <Card className="border-border"><CardContent className="pt-6 text-sm text-muted-text">پروژه‌ای برای مدیریت وجود ندارد.</CardContent></Card>}
          </div>
        )}
      </Main>
    </div>
  )
}
