import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { listProjects, deleteProject, createProject, type ProjectRead, type ProjectCreate } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { toast } from 'sonner'

const PERSIAN_DIGITS = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹']
function toPersianDigits(s: string | number) { return String(s).replace(/[0-9]/g, d => PERSIAN_DIGITS[+d]) }

export function relativeDate(value: string) {
  const d = new Date(value)
  if (isNaN(d.getTime())) return '—'
  const diff = Date.now() - d.getTime()
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)
  if (minutes < 1) return 'همین الان'
  if (minutes < 60) return toPersianDigits(minutes) + ' دقیقه پیش'
  if (hours < 24) return toPersianDigits(hours) + ' ساعت پیش'
  if (days < 30) return toPersianDigits(days) + ' روز پیش'
  const months = Math.floor(days / 30)
  if (months < 12) return toPersianDigits(months) + ' ماه پیش'
  return toPersianDigits(Math.floor(days / 365)) + ' سال پیش'
}

export function ProjectGrid() {
  const navigate = useNavigate()
  const [projects, setProjects] = useState<ProjectRead[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [sort, setSort] = useState('newest')
  const [showCreate, setShowCreate] = useState(false)
  const [creating, setCreating] = useState(false)
  const [newProject, setNewProject] = useState<ProjectCreate>({ name: '', description: '', website_url: '' })

  const fetchProjects = useCallback(async () => {
    setLoading(true)
    try { setProjects(await listProjects()) }
    catch { setProjects([]); toast.error('دریافت پروژه‌ها ممکن نشد.') }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { fetchProjects() }, [fetchProjects])

  const handleCreate = async () => {
    if (!newProject.name.trim()) return
    setCreating(true)
    try {
      await createProject({ name: newProject.name.trim(), description: newProject.description?.trim() || null, website_url: newProject.website_url?.trim() || null })
      toast.success('پروژه ساخته شد')
      setShowCreate(false)
      setNewProject({ name: '', description: '', website_url: '' })
      fetchProjects()
    } catch { toast.error('خطا در ساخت پروژه') }
    finally { setCreating(false) }
  }

  const filtered = projects.filter(p => !search || p.name.toLowerCase().includes(search.toLowerCase())).sort((a, b) => {
    if (sort === 'newest') return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    if (sort === 'oldest') return new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
    if (sort === 'za') return (b.name || '').localeCompare(a.name || '', 'fa')
    return (a.name || '').localeCompare(b.name || '', 'fa')
  })

  const handleDelete = async (e: React.MouseEvent, project: ProjectRead) => {
    e.stopPropagation()
    if (!window.confirm(`پروژه «${project.name || 'بدون نام'}» حذف شود؟`)) return
    try { await deleteProject(project.id); setProjects(prev => prev.filter(p => p.id !== project.id)); toast.success('پروژه حذف شد') }
    catch { toast.error('خطا در حذف پروژه') }
  }

  return (
    <div className="bg-bg font-vazirmatn min-h-full" dir="rtl">
      <Header fixed className="bg-bg">
        <h1 className="text-lg font-black">پروژه‌های من</h1>
      </Header>
      <Main fixed>
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-medium text-muted-text">همه پروژه‌ها در یک نگاه</p>
          </div>
          <Button onClick={() => setShowCreate(true)} className="border-border bg-accent-neon text-fg shadow-[4px_4px_0_var(--color-shadow)] hover:bg-accent-neon/90 font-bold">
            + پروژه جدید
          </Button>
        </div>

        <div className="mb-6 flex flex-col gap-3 sm:flex-row">
          <div className="relative flex-1">
            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-text pointer-events-none select-none">⌕</span>
            <Input
              placeholder="جستجو بر اساس نام پروژه"
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="border-border pr-10 font-medium"
            />
          </div>
          <Select value={sort} onValueChange={setSort}>
            <SelectTrigger className="w-full border-border font-medium sm:w-[200px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="newest">جدیدترین</SelectItem>
              <SelectItem value="oldest">قدیمی‌ترین</SelectItem>
              <SelectItem value="az">الفبایی: الف تا ی</SelectItem>
              <SelectItem value="za">الفبایی: ی تا الف</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="mb-4 text-sm font-bold text-muted-text">{toPersianDigits(filtered.length)} پروژه</div>

        {loading && (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <Card key={i} className="border-border shadow-[6px_6px_0_var(--color-shadow)]">
                <CardHeader><Skeleton className="h-5 w-3/4 bg-accent" /></CardHeader>
                <CardContent className="space-y-3">
                  <Skeleton className="h-4 w-full bg-accent" />
                  <Skeleton className="h-4 w-5/6 bg-accent" />
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {!loading && filtered.length === 0 && (
          <div className="flex flex-col items-center gap-4 rounded-none border-3 border-border bg-card p-10 text-center shadow-[6px_6px_0_var(--color-shadow)]">
            <h2 className="text-xl font-black">هنوز پروژه‌ای نداری</h2>
            <p className="text-sm font-medium text-muted-text">با ساخت پروژه جدید شروع کن.</p>
            <Button onClick={() => setShowCreate(true)} className="border-border bg-accent-neon text-fg shadow-[4px_4px_0_var(--color-shadow)] hover:bg-accent-neon/90 font-bold">
              + پروژه جدید
            </Button>
          </div>
        )}

        {!loading && filtered.length > 0 && (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {filtered.map(project => (
              <Card
                key={project.id}
                onClick={e => { if ((e.target as HTMLElement).closest('.del-btn')) return; navigate({ to: '/projects/' + project.id }) }}
                className="cursor-pointer border-border shadow-[6px_6px_0_var(--color-shadow)] transition-transform hover:-translate-x-0.5 hover:-translate-y-0.5"
              >
                <CardHeader className="flex-row items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <CardTitle className="text-lg leading-tight">{project.name || 'پروژه بدون نام'}</CardTitle>
                    <CardDescription className="mt-2 line-clamp-2 text-sm font-medium text-muted-text">
                      {project.description || 'بدون توضیح'}
                    </CardDescription>
                  </div>
                  <button
                    type="button"
                    className="del-btn flex size-9 shrink-0 items-center justify-center border-3 border-border bg-card text-fg hover:shadow-[2px_2px_0_var(--color-shadow)] transition-shadow"
                    aria-label={`حذف ${project.name || ''}`}
                    onClick={e => handleDelete(e, project)}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                    </svg>
                  </button>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center justify-between gap-2">
                    <span className="inline-block border-2 border-border bg-card px-2 py-1 text-xs font-bold text-muted-text">
                      ساخته شده: {relativeDate(project.created_at)}
                    </span>
                    <span
                      className="cursor-pointer text-sm font-bold"
                      onClick={e => { e.stopPropagation(); navigate({ to: '/projects/' + project.id }) }}
                    >
                      جزئیات ←
                    </span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </Main>

      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="rounded-none border-3 border-border bg-card shadow-[6px_6px_0_var(--color-shadow)] font-vazirmatn">
          <DialogHeader>
            <DialogTitle className="text-xl font-black">پروژه جدید</DialogTitle>
            <DialogDescription className="font-medium text-muted-text">اطلاعات پروژه جدید را وارد کنید.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-bold">نام پروژه</label>
              <Input
                placeholder="مثال: فروشگاه آنلاین"
                value={newProject.name}
                onChange={e => setNewProject(p => ({ ...p, name: e.target.value }))}
                className="border-border font-medium"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-bold">توضیحات <span className="font-medium text-muted-text">(اختیاری)</span></label>
              <textarea
                placeholder="توضیح کوتاهی..."
                value={newProject.description || ''}
                onChange={e => setNewProject(p => ({ ...p, description: e.target.value }))}
                rows={3}
                className="w-full rounded-none border-3 border-border p-3 font-medium outline-none resize-y font-vazirmatn"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-bold">آدرس وب‌سایت <span className="font-medium text-muted-text">(اختیاری)</span></label>
              <Input
                placeholder="https://example.com"
                value={newProject.website_url || ''}
                onChange={e => setNewProject(p => ({ ...p, website_url: e.target.value }))}
                className="border-border font-medium"
              />
            </div>
          </div>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setShowCreate(false)} className="border-border font-bold">انصراف</Button>
            <Button
              disabled={!newProject.name.trim() || creating}
              onClick={handleCreate}
              className="border-border bg-accent-neon text-fg shadow-[4px_4px_0_var(--color-shadow)] hover:bg-accent-neon/90 font-bold disabled:opacity-50"
            >
              {creating ? 'در حال ساخت...' : 'ساخت پروژه'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
