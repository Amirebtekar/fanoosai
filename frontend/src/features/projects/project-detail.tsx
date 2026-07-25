import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from '@tanstack/react-router'
import { getErrorMessage, getProject, getProjectRuns, type ProjectRead, type ProjectRun } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { ProjectManagementSections } from './project-management'
import { toast } from 'sonner'

export function ProjectDetailPage() {
  const { id } = useParams({ from: '/_authenticated/projects_/$id' })
  const navigate = useNavigate()
  const [project, setProject] = useState<ProjectRead | null>(null)

  useEffect(() => { getProject(Number(id)).then(setProject).catch(e => toast.error(getErrorMessage(e, 'خطا در دریافت پروژه'))) }, [id])

  if (!project) return <div className="min-h-full bg-bg p-6 font-vazirmatn" dir="rtl"><Skeleton className="h-32 w-full bg-accent" /></div>

  return <div className="min-h-full bg-bg font-vazirmatn" dir="rtl">
    <Header fixed className="bg-bg"><div className="flex items-center gap-3"><Button variant="outline" onClick={() => navigate({ to: '/projects' })} className="border-border font-bold">← بازگشت</Button><h1 className="text-lg font-black">{project.name}</h1></div></Header>
    <Main fixed><ProjectManagementSections projectId={Number(id)} /><ProjectRuns projectId={Number(id)} /></Main>
  </div>
}

function ProjectRuns({ projectId }: { projectId: number }) {
  const [page, setPage] = useState(1)
  const [runs, setRuns] = useState<ProjectRun[]>([])
  const [total, setTotal] = useState(0)
  const load = useCallback(() => getProjectRuns(projectId, page).then(result => { setRuns(result.items); setTotal(result.total) }).catch(e => toast.error(getErrorMessage(e, 'خطا در دریافت اجراها'))), [projectId, page])

  useEffect(() => { void load() }, [load])

  return <section className="mb-8"><h2 className="mb-4 text-lg font-black">گزارش اجراها ({total})</h2><div className="space-y-2">{runs.map(run => <div key={run.ai_run_id} className="border-2 border-border bg-card p-3 text-sm"><div className="flex justify-between gap-3 font-bold"><span>{run.ai_model}</span><span>{run.status}</span></div><p className="mt-1 truncate text-muted-text">{run.prompt}</p><p className="mt-1 text-xs text-muted-text">{new Date(run.created_at).toLocaleString('fa-IR')}</p></div>)}{!runs.length && <p className="text-sm text-muted-text">اجرایی ثبت نشده است.</p>}</div>{total > 20 && <div className="mt-3 flex gap-2"><Button variant="outline" size="sm" disabled={page === 1} onClick={() => setPage(page - 1)}>قبلی</Button><Button variant="outline" size="sm" disabled={page * 20 >= total} onClick={() => setPage(page + 1)}>بعدی</Button></div>}</section>
}
