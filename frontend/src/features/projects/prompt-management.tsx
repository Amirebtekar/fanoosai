import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { addPromptModel, archivePrompt, createPrompt, getErrorMessage, getExecutionAvailability, listAIModels, listPrompts, removePromptModel, restorePrompt, runPrompt, type AIModelRead, type PromptModelExecutionAvailability, type PromptRead } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { AddModelMenu, ModelMultiSelect } from './model-picker'

export function promptLines(value: string) {
  return value.split(/\r?\n/).map(line => line.trim()).filter(Boolean)
}

export async function runAvailablePromptModels(
  models: PromptModelExecutionAvailability[],
  run: (modelId: number) => Promise<unknown>,
) {
  const available = models.filter(model => model.can_run)
  if (!available.length) throw new Error('همه مدل‌ها امروز اجرا شده‌اند.')
  return Promise.all(available.map(model => run(model.model_id)))
}

export function PromptManagement({ projectId }: { projectId: number }) {
  const navigate = useNavigate()
  const [prompts, setPrompts] = useState<PromptRead[]>([])
  const [models, setModels] = useState<AIModelRead[]>([])
  const [availability, setAvailability] = useState<Record<number, PromptModelExecutionAvailability[]>>({})
  const [text, setText] = useState('')
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [creating, setCreating] = useState(false)
  const [showCreate, setShowCreate] = useState(false)

  const load = useCallback(async () => {
    try {
      const [promptData, modelData] = await Promise.all([listPrompts(projectId, true), listAIModels()])
      setPrompts(promptData)
      setModels(modelData)
      const active = promptData.filter(p => p.is_active)
      const entries = await Promise.all(active.map(async p => [p.id, await getExecutionAvailability(projectId, p.id)] as const))
      setAvailability(Object.fromEntries(entries))
    } catch (e) {
      toast.error(getErrorMessage(e, 'خطا در دریافت پرامپت‌ها'))
    }
  }, [projectId])

  useEffect(() => { void Promise.resolve().then(load) }, [load])

  const create = async () => {
    const promptTexts = promptLines(text)
    if (!promptTexts.length || !selectedIds.length) return
    setCreating(true)
    try {
      await Promise.all(promptTexts.map(promptText => createPrompt(projectId, { text: promptText, model_ids: selectedIds })))
      toast.success(`${promptTexts.length} پرامپت ساخته شد`)
      setText('')
      setSelectedIds([])
      setShowCreate(false)
      await load()
    } catch (e) {
      toast.error(getErrorMessage(e, 'خطا در ساخت پرامپت'))
    } finally {
      setCreating(false)
    }
  }

  const update = async (action: () => Promise<unknown>, success: string, fallback: string) => {
    try { await action(); toast.success(success); await load() }
    catch (e) { toast.error(getErrorMessage(e, fallback)) }
  }
  const active = prompts.filter(prompt => prompt.is_active)
  const archived = prompts.filter(prompt => !prompt.is_active)

  return (
    <section className="mb-8">
      <Button onClick={() => setShowCreate(true)} className="mb-8 border-border bg-accent-neon text-primary-foreground shadow-[4px_4px_0_var(--color-shadow)] hover:bg-accent-neon/90 font-bold">+ پرامپت جدید</Button>

      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-h-[90vh] w-[min(96vw,44rem)] overflow-y-auto rounded-none border-3 border-border bg-card shadow-[6px_6px_0_var(--color-shadow)] font-vazirmatn">
          <DialogHeader>
            <DialogTitle className="text-xl font-black">پرامپت جدید</DialogTitle>
            <DialogDescription className="font-medium text-muted-text">هر خط یک پرامپت جداگانه است؛ مدل‌های انتخاب‌شده برای همه اعمال می‌شود.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
          <label htmlFor="prompt-batch-text" className="block text-sm font-bold">متن پرامپت‌ها</label>
          <textarea id="prompt-batch-text" value={text} onChange={e => setText(e.target.value)} placeholder="هر خط یک پرامپت..." rows={3} className="w-full resize-y rounded-none border-3 border-border p-3 font-medium outline-none font-vazirmatn" />
          <details open className="border-2 border-border">
            <summary className="flex cursor-pointer items-center justify-between px-3 py-2 text-sm font-bold">
              <span>انتخاب مدل</span>
              <span className="text-xs font-medium text-muted-text">{selectedIds.length ? `${selectedIds.length} انتخاب شده` : `${models.length} مدل فعال`}</span>
            </summary>
            <div className="border-t-2 border-border p-3">
              <ModelMultiSelect
                models={models}
                selectedIds={selectedIds}
                onToggle={id => setSelectedIds(current => current.includes(id) ? current.filter(value => value !== id) : [...current, id])}
                onClear={() => setSelectedIds([])}
              />
            </div>
          </details>
          </div>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setShowCreate(false)} className="border-border font-bold">انصراف</Button>
            <Button disabled={!promptLines(text).length || !selectedIds.length || creating} onClick={create} className="border-border bg-accent-neon text-primary-foreground shadow-[4px_4px_0_var(--color-shadow)] hover:bg-accent-neon/90 font-bold disabled:opacity-50">{creating ? 'در حال ساخت...' : 'ساخت پرامپت‌ها'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <h2 className="mb-4 text-lg font-black">پرامپت‌های فعال ({active.length})</h2>
      <div className="space-y-4">
        {active.map(prompt => {
          const promptAvailability = availability[prompt.id]
          const canRun = !promptAvailability || promptAvailability.some(m => m.can_run)
          return <PromptCard key={prompt.id} prompt={prompt} allModels={models} runDisabled={!canRun} onRun={canRun ? () => update(async () => {
            const available = await getExecutionAvailability(projectId, prompt.id)
            return runAvailablePromptModels(available, modelId => runPrompt(projectId, prompt.id, modelId))
          }, 'اجرا در صف قرار گرفت', 'خطا در اجرای پرامپت') : undefined} onArchive={() => update(() => archivePrompt(projectId, prompt.id), 'پرامپت بایگانی شد', 'خطا در بایگانی')} onAddModel={modelId => update(() => addPromptModel(projectId, prompt.id, modelId), 'مدل اضافه شد', 'خطا در افزودن مدل')} onRemoveModel={modelId => update(() => removePromptModel(projectId, prompt.id, modelId), 'مدل حذف شد', 'خطا در حذف مدل')} onNavigate={() => navigate({ to: '/projects/' + projectId + '/prompts/' + prompt.id })} />
        })}
        {!active.length && <p className="text-sm font-medium text-muted-text">پرامپت فعالی وجود ندارد.</p>}
      </div>

      {!!archived.length && <details className="mt-8 border-2 border-border bg-card shadow-[6px_6px_0_var(--color-shadow)]"><summary className="cursor-pointer px-6 py-4 text-lg font-black">بایگانی ({archived.length})</summary><div className="space-y-4 p-6"><p className="text-sm text-muted-text">پرامپت‌های بایگانی‌شده پس از ۳۰ روز حذف می‌شوند.</p>{archived.map(prompt => <PromptCard key={prompt.id} prompt={prompt} allModels={models} onRestore={() => update(() => restorePrompt(projectId, prompt.id), 'پرامپت بازگردانی شد', 'خطا در بازگردانی')} onNavigate={() => navigate({ to: '/projects/' + projectId + '/prompts/' + prompt.id })} />)}</div></details>}
    </section>
  )
}

function daysUntilArchiveRemoval(archivedAt: string) {
  return Math.max(0, Math.ceil((Date.parse(archivedAt) + 30 * 24 * 60 * 60 * 1000 - Date.now()) / (24 * 60 * 60 * 1000)))
}

type PromptCardProps = { prompt: PromptRead; allModels: AIModelRead[]; runDisabled?: boolean; onRun?: () => void; onArchive?: () => void; onRestore?: () => void; onAddModel?: (id: number) => void; onRemoveModel?: (id: number) => void; onNavigate: () => void }

function PromptCard(props: PromptCardProps) {
  const [isRunning, setIsRunning] = useState(false)
  const run = async () => {
    setIsRunning(true)
    try { await props.onRun?.() }
    finally { setIsRunning(false) }
  }

  return <div className="space-y-2">
    <div className={isRunning ? 'pointer-events-none opacity-70' : undefined}><PromptCardStatic {...props} onRun={props.onRun ? run : undefined} /></div>
    {isRunning && <div role="status" aria-live="polite" className="overflow-hidden border-2 border-border bg-card p-3 text-sm font-bold"><div className="mb-2 flex items-center gap-2"><Loader2 className="size-4 animate-spin" aria-hidden="true" />در حال اجرای پرامپت...</div><div className="h-1.5 overflow-hidden bg-muted"><div className="h-full w-1/2 animate-pulse bg-accent-neon" /></div></div>}
    <p className="px-1 text-xs font-medium text-muted-text">آخرین اجرا: {props.prompt.last_run_at ? new Date(props.prompt.last_run_at).toLocaleString('fa-IR') : 'هنوز اجرا نشده'}</p>
  </div>
}

function PromptCardStatic({ prompt, allModels, runDisabled, onRun, onArchive, onRestore, onAddModel, onRemoveModel, onNavigate }: PromptCardProps) {
  const available = allModels.filter(model => !prompt.models.some(selected => selected.id === model.id))
  return <Card onClick={e => { if ((e.target as HTMLElement).closest('.prompt-action')) return; onNavigate() }} className="cursor-pointer border-border shadow-[6px_6px_0_var(--color-shadow)]"><CardHeader className="flex-row items-start justify-between gap-3"><p className="flex-1 whitespace-pre-wrap text-sm font-medium leading-relaxed">{prompt.text}</p><div className="flex shrink-0 gap-2">{onRun && <button type="button" disabled={runDisabled} title={runDisabled ? 'مدل قابل اجرایی برای امروز باقی نمانده است' : undefined} className="prompt-action border-3 border-border bg-accent-neon px-3 py-1.5 text-xs font-bold disabled:cursor-not-allowed disabled:opacity-40" onClick={onRun}>{runDisabled ? 'انجام شد' : 'اجرا'}</button>}{onArchive && <button type="button" className="prompt-action border-3 border-border bg-card px-3 py-1.5 text-xs font-bold" onClick={onArchive}>بایگانی</button>}{onRestore && <button type="button" className="prompt-action border-3 border-border bg-accent-neon px-3 py-1.5 text-xs font-bold" onClick={onRestore}>بازگردانی</button>}</div></CardHeader><CardContent><div className="flex flex-wrap items-center gap-2">{prompt.models.map(model => <span key={model.id} className={`prompt-action inline-flex items-center gap-1 border-2 px-2 py-0.5 text-xs font-bold ${model.is_active ? 'border-border' : 'border-destructive/60 text-muted-text opacity-80'}`}>{model.name}{!model.is_active && <span className="border border-destructive/60 bg-destructive/10 px-1 py-px text-[10px] font-black text-destructive">منسوخ شده</span>}{onRemoveModel && <button type="button" title="حذف مدل" aria-label={`حذف ${model.name}`} onClick={() => onRemoveModel(model.id)}>×</button>}</span>)}{onAddModel && <AddModelMenu models={available} onAdd={onAddModel} />}</div>{!prompt.is_active && <p className="mt-3 text-xs font-bold text-muted-text">حذف خودکار تا {daysUntilArchiveRemoval(prompt.updated_at)} روز دیگر</p>}</CardContent></Card>
}
