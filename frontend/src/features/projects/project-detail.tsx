import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useParams } from '@tanstack/react-router'
import { getProject, listPrompts, createPrompt, archivePrompt, restorePrompt, addPromptModel, removePromptModel, listAIModels, getErrorMessage, type ProjectRead, type PromptRead, type AIModelRead } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { toast } from 'sonner'

const PERSIAN_DIGITS = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹']
function toPersianDigits(s: string | number) { return String(s).replace(/[0-9]/g, d => PERSIAN_DIGITS[+d]) }

export function ProjectDetailPage() {
  const { id } = useParams({ from: '/_authenticated/projects_/$id' })
  const navigate = useNavigate()
  const [project, setProject] = useState<ProjectRead | null>(null)
  const [prompts, setPrompts] = useState<PromptRead[]>([])
  const [allModels, setAllModels] = useState<AIModelRead[]>([])
  const [loading, setLoading] = useState(true)
  const [newPromptText, setNewPromptText] = useState('')
  const [selectedModelIds, setSelectedModelIds] = useState<number[]>([])
  const [creating, setCreating] = useState(false)

  const fetchData = useCallback(async () => {
    setLoading(true)
    try { const [proj, promptsData, models] = await Promise.all([getProject(Number(id)), listPrompts(Number(id), true), listAIModels()]); setProject(proj); setPrompts(promptsData); setAllModels(models) }
    catch (e) { toast.error(getErrorMessage(e, 'خطا در دریافت اطلاعات')) }
    finally { setLoading(false) }
  }, [id])

  useEffect(() => { fetchData() }, [fetchData])

  const handleCreatePrompt = async () => {
    if (!newPromptText.trim()) return; setCreating(true)
    try { await createPrompt(Number(id), { text: newPromptText.trim(), model_ids: selectedModelIds.length ? selectedModelIds : undefined }); toast.success('پرامپت ساخته شد'); setNewPromptText(''); setSelectedModelIds([]); fetchData() }
    catch { toast.error('خطا در ساخت پرامپت') }
    finally { setCreating(false) }
  }

  const handleArchive = async (promptId: number) => { try { await archivePrompt(Number(id), promptId); toast.success('پرامپت بایگانی شد'); fetchData() } catch { toast.error('خطا در بایگانی') } }
  const handleRestore = async (promptId: number) => { try { await restorePrompt(Number(id), promptId); toast.success('پرامپت به لیست فعال برگشت'); fetchData() } catch (e) { toast.error(getErrorMessage(e, 'خطا در بازگردانی پرامپت')) } }
  const handleAddModel = async (promptId: number, modelId: number) => { try { await addPromptModel(Number(id), promptId, modelId); toast.success('مدل اضافه شد'); fetchData() } catch { toast.error('خطا در افزودن مدل') } }
  const handleRemoveModel = async (promptId: number, modelId: number) => { try { await removePromptModel(Number(id), promptId, modelId); toast.success('مدل حذف شد'); fetchData() } catch { toast.error('خطا در حذف مدل') } }

  const activePrompts = prompts.filter(p => p.is_active)
  const archivedPrompts = prompts.filter(p => !p.is_active)
  const modelsNotInPrompt = (prompt: PromptRead) => allModels.filter(m => !prompt.models.some(pm => pm.id === m.id))

  if (loading) return (
    <div className="min-h-full bg-bg p-6 font-vazirmatn" dir="rtl">
      <Skeleton className="mb-4 h-8 w-48 bg-accent" />
      <Skeleton className="mb-8 h-4 w-72 bg-accent" />
      <div className="space-y-4">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-24 w-full bg-accent" />)}</div>
    </div>
  )
  if (!project) return <div className="min-h-full bg-bg p-6 font-vazirmatn" dir="rtl"><p>پروژه یافت نشد</p></div>

  return (
    <div className="min-h-full bg-bg font-vazirmatn" dir="rtl">
      <Header fixed className="bg-bg">
        <div className="flex items-center gap-3">
          <Button variant="outline" onClick={() => navigate({ to: '/projects' })} className="border-border font-bold">
            ← بازگشت
          </Button>
          <h1 className="text-lg font-black">{project.name}</h1>
        </div>
      </Header>
      <Main fixed>
        {project.description && <p className="mb-6 text-sm font-medium text-muted-text">{project.description}</p>}

        <Card className="mb-8 border-border shadow-[6px_6px_0_var(--color-shadow)]">
          <CardHeader>
            <CardTitle className="text-lg font-black">پرامپت جدید</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <textarea
              placeholder="متن پرامپت را وارد کنید..."
              value={newPromptText}
              onChange={e => setNewPromptText(e.target.value)}
              rows={3}
              className="w-full rounded-none border-3 border-border p-3 font-medium outline-none resize-y font-vazirmatn"
            />
            <ModelSelector models={allModels} selectedIds={selectedModelIds} onToggle={(id) => setSelectedModelIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id])} />
            <Button
              disabled={!newPromptText.trim() || creating}
              onClick={handleCreatePrompt}
              className="border-border bg-accent-neon text-fg shadow-[4px_4px_0_var(--color-shadow)] hover:bg-accent-neon/90 font-bold disabled:opacity-50"
            >
              {creating ? 'در حال ساخت...' : 'ساخت پرامپت'}
            </Button>
          </CardContent>
        </Card>

        <h2 className="mb-4 text-lg font-black">پرامپت‌های فعال ({toPersianDigits(activePrompts.length)})</h2>
        <div className="mb-8 space-y-4">
          {activePrompts.map(prompt => (
            <PromptCard key={prompt.id} prompt={prompt} modelsNotInPrompt={modelsNotInPrompt} onArchive={() => handleArchive(prompt.id)} onAddModel={(mid) => handleAddModel(prompt.id, mid)} onRemoveModel={(mid) => handleRemoveModel(prompt.id, mid)} onNavigate={() => navigate({ to: '/projects/' + id + '/prompts/' + prompt.id })} />
          ))}
          {activePrompts.length === 0 && <p className="text-sm font-medium text-muted-text">پرامپت فعالی وجود ندارد</p>}
        </div>

        {archivedPrompts.length > 0 && (
          <>
            <h2 className="mb-4 text-lg font-black">بایگانی ({toPersianDigits(archivedPrompts.length)})</h2>
            <div className="mb-8 space-y-4">
              {archivedPrompts.map(prompt => (
            <PromptCard key={prompt.id} prompt={prompt} modelsNotInPrompt={modelsNotInPrompt} onArchive={() => {}} onRestore={() => handleRestore(prompt.id)} onAddModel={(mid) => handleAddModel(prompt.id, mid)} onRemoveModel={(mid) => handleRemoveModel(prompt.id, mid)} onNavigate={() => navigate({ to: '/projects/' + id + '/prompts/' + prompt.id })} archived />
              ))}
            </div>
          </>
        )}
      </Main>
    </div>
  )
}

function ModelSelector({ models, selectedIds, onToggle }: { models: AIModelRead[]; selectedIds: number[]; onToggle: (id: number) => void }) {
  const [search, setSearch] = useState('')
  const filtered = models.filter(m => !search || m.name.toLowerCase().includes(search.toLowerCase()))

  return (
    <div>
      <input
        type="text"
        placeholder="جستجوی مدل..."
        value={search}
        onChange={e => setSearch(e.target.value)}
        className="mb-2 w-full rounded-none border-3 border-border p-2.5 font-medium outline-none font-vazirmatn"
      />
      <div className="flex max-h-40 flex-wrap gap-2 overflow-y-auto">
        {filtered.map(m => (
          <label key={m.id} className="flex cursor-pointer items-center gap-2 font-medium">
            <input type="checkbox" checked={selectedIds.includes(m.id)} onChange={() => onToggle(m.id)} className="size-4 accent-accent-neon" />
            {m.name}
          </label>
        ))}
        {filtered.length === 0 && <span className="p-1 text-sm text-muted-text">مدلی یافت نشد</span>}
      </div>
      {selectedIds.length > 0 && <div className="mt-1.5 text-xs text-muted-text">{selectedIds.length} مدل انتخاب شده</div>}
    </div>
  )
}

function ModelDropdown({ models, onSelect }: { models: AIModelRead[]; onSelect: (id: number) => void }) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const filtered = models.filter(m => !search || m.name.toLowerCase().includes(search.toLowerCase()))

  return (
    <div className="relative">
      <button type="button" onClick={() => { setOpen(!open); setSearch('') }} className="border-2 border-border bg-accent-neon text-fg px-2 py-0.5 text-xs font-bold cursor-pointer font-vazirmatn">
        + مدل
      </button>
      {open && (
        <div className="absolute left-0 top-full z-10 mt-1 min-w-[180px] border-3 border-border bg-card p-2 shadow-[6px_6px_0_var(--color-shadow)]">
          <input
            type="text"
            placeholder="جستجو..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            autoFocus
            className="mb-1 w-full rounded-none border-2 border-border p-1.5 text-xs font-medium outline-none font-vazirmatn"
          />
          <div className="max-h-36 overflow-y-auto">
            {filtered.map(m => (
              <button key={m.id} type="button" onClick={() => { onSelect(m.id); setOpen(false) }}
                className="block w-full px-2 py-1.5 text-right text-xs font-medium hover:bg-accent cursor-pointer font-vazirmatn">
                {m.name}
              </button>
            ))}
            {filtered.length === 0 && <span className="block p-1 text-xs text-muted-text">مدلی یافت نشد</span>}
          </div>
        </div>
      )}
    </div>
  )
}

function PromptCard({ prompt, modelsNotInPrompt, onArchive, onRestore, onAddModel, onRemoveModel, onNavigate, archived }: {
  prompt: PromptRead; modelsNotInPrompt: (p: PromptRead) => AIModelRead[]; onArchive: () => void; onRestore?: () => void; onAddModel: (id: number) => void; onRemoveModel: (id: number) => void; onNavigate: () => void; archived?: boolean
}) {
  const available = modelsNotInPrompt(prompt)

  return (
    <Card
      onClick={(e) => { if ((e.target as HTMLElement).closest('.prompt-btn, .model-tag, .model-add-area')) return; onNavigate() }}
      className={`cursor-pointer border-border shadow-[6px_6px_0_var(--color-shadow)] transition-transform hover:-translate-x-0.5 hover:-translate-y-0.5 ${archived ? 'opacity-70' : ''}`}
    >
      <CardHeader className="flex-row items-start justify-between gap-3">
        <p className="flex-1 whitespace-pre-wrap text-sm font-medium leading-relaxed">{prompt.text}</p>
        {!archived && (
          <div className="flex shrink-0 gap-2">
            <button type="button" onClick={onArchive} className="prompt-btn border-3 border-border bg-card px-3 py-1.5 text-xs font-bold cursor-pointer font-vazirmatn hover:shadow-[2px_2px_0_var(--color-shadow)] transition-shadow">بایگانی</button>
          </div>
        )}
        {archived && (
          <div className="flex shrink-0 gap-2">
            <button type="button" onClick={() => onRestore?.()} className="prompt-btn border-3 border-border bg-accent-neon text-fg px-3 py-1.5 text-xs font-bold cursor-pointer font-vazirmatn hover:shadow-[2px_2px_0_var(--color-shadow)] transition-shadow">بازگردانی</button>
          </div>
        )}
      </CardHeader>
      <CardContent>
        <p className="mb-3 text-xs font-medium text-muted-text">
          آخرین اجرا: {prompt.last_run_at ? new Date(prompt.last_run_at).toLocaleString('fa-IR') : 'هنوز اجرا نشده'}
        </p>
        <div className="flex flex-wrap items-center gap-2">
          {prompt.models.map(m => (
            <span key={m.id} className="model-tag inline-flex items-center gap-1 border-2 border-border bg-card px-2 py-0.5 text-xs font-bold">
              {m.name}
              {!archived && (
                <button type="button" onClick={() => onRemoveModel(m.id)} className="cursor-pointer border-none bg-transparent p-0 leading-none text-muted-text font-vazirmatn">×</button>
              )}
            </span>
          ))}
          {!archived && available.length > 0 && (
            <span className="model-add-area"><ModelDropdown models={available} onSelect={(id) => onAddModel(id)} /></span>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
