import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  getProject, listPrompts, createPrompt, archivePrompt,
  addPromptModel, removePromptModel, runPrompt,
  listAIModels,
  logout,
  type ProjectRead, type PromptRead, type AIModelRead,
} from '../lib/api'

const S = {
  bg: '#f5f0e8', surface: '#ffffff', fg: '#161616',
  muted: '#66625d', border: '#161616', accent: '#c6ff40',
  shadow: '6px 6px 0 #161616',
}

function relativeDate(value: string) {
  const d = new Date(value)
  if (isNaN(d.getTime())) return '—'
  const diff = Date.now() - d.getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return 'همین الان'
  if (minutes < 60) return minutes + ' دقیقه پیش'
  const hours = Math.floor(diff / 3600000)
  if (hours < 24) return hours + ' ساعت پیش'
  const days = Math.floor(diff / 86400000)
  if (days < 30) return days + ' روز پیش'
  return Math.floor(days / 365) + ' سال پیش'
}

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [project, setProject] = useState<ProjectRead | null>(null)
  const [prompts, setPrompts] = useState<PromptRead[]>([])
  const [allModels, setAllModels] = useState<AIModelRead[]>([])
  const [loading, setLoading] = useState(true)
  const [promptsLoading, setPromptsLoading] = useState(true)
  const [toast, setToast] = useState('')
  const [runningId, setRunningId] = useState<number | null>(null)

  /* create form */
  const [showForm, setShowForm] = useState(false)
  const [newText, setNewText] = useState('')
  const [selectedModels, setSelectedModels] = useState<number[]>([])
  const [creating, setCreating] = useState(false)

  /* model add dropdown per prompt */
  const [addingModelFor, setAddingModelFor] = useState<number | null>(null)

  const showToast = (msg: string) => {
    setToast(msg)
    setTimeout(() => setToast(''), 3000)
  }

  const load = () => {
    if (!id) return
    setLoading(true)
    setPromptsLoading(true)
    getProject(Number(id)).then(setProject).catch(() => setProject(null)).finally(() => setLoading(false))
    listPrompts(Number(id), true).then(setPrompts).catch(() => setPrompts([])).finally(() => setPromptsLoading(false))
    listAIModels().then(setAllModels).catch(() => {})
  }

  useEffect(() => { load() }, [id])

  const availableModelsForPrompt = (prompt: PromptRead) =>
    allModels.filter(m => !prompt.models.some(pm => pm.id === m.id))

  const handleCreate = async () => {
    if (!newText.trim() || !id) return
    setCreating(true)
    try {
      await createPrompt(Number(id), { text: newText.trim(), model_ids: selectedModels.length ? selectedModels : undefined })
      showToast('پرامپت با موفقیت ساخته شد')
      setNewText('')
      setSelectedModels([])
      setShowForm(false)
      listPrompts(Number(id), true).then(setPrompts).catch(() => {})
    } catch {
      showToast('خطا در ساخت پرامپت')
    } finally {
      setCreating(false)
    }
  }

  const handleArchive = async (promptId: number) => {
    if (!id) return
    try {
      await archivePrompt(Number(id), promptId)
      showToast('پرامپت بایگانی شد')
      listPrompts(Number(id), true).then(setPrompts).catch(() => {})
    } catch {
      showToast('خطا در بایگانی پرامپت')
    }
  }

  const handleAddModel = async (promptId: number, modelId: number) => {
    if (!id) return
    try {
      await addPromptModel(Number(id), promptId, modelId)
      showToast('مدل با موفقیت اضافه شد')
      setAddingModelFor(null)
      listPrompts(Number(id), true).then(setPrompts).catch(() => {})
    } catch {
      showToast('خطا در افزودن مدل')
    }
  }

  const handleRemoveModel = async (promptId: number, modelId: number) => {
    if (!id) return
    try {
      await removePromptModel(Number(id), promptId, modelId)
      showToast('مدل حذف شد')
      listPrompts(Number(id), true).then(setPrompts).catch(() => {})
    } catch {
      showToast('خطا در حذف مدل')
    }
  }

  const handleRun = async (promptId: number) => {
    if (!id) return
    setRunningId(promptId)
    try {
      const results = await runPrompt(Number(id), promptId)
      const ok = results.filter(r => r.ai_run_status === 'success').length
      showToast(`اجرا شد: ${ok} موفق از ${results.length} مدل`)
    } catch {
      showToast('خطا در اجرای پرامپت')
    } finally {
      setRunningId(null)
    }
  }

  const userRaw = localStorage.getItem('user')
  let userName = 'کاربر'
  if (userRaw) {
    try { const u = JSON.parse(userRaw); userName = [u.first_name, u.last_name].filter(Boolean).join(' ') || u.phone || 'کاربر' } catch {}
  }

  const handleLogout = () => {
    void logout().finally(() => {
      localStorage.removeItem('user')
      navigate('/login')
    })
  }

  if (loading) {
    return (
      <div style={{ minHeight: '100%', background: S.bg, color: S.fg, fontFamily: "'Vazirmatn', system-ui, sans-serif", display: 'grid', placeItems: 'center', padding: 40 }}>
        <div style={{ display: 'grid', gap: 16, width: '100%', maxWidth: 600 }}>
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} style={{ padding: 18, height: 60, background: 'linear-gradient(90deg, #fff 25%, #f0ede7 37%, #fff 63%)', backgroundSize: '400% 100%', animation: 'shimmer 1.2s infinite', border: '3px solid ' + S.border, boxShadow: S.shadow }} />
          ))}
        </div>
        <style>{`@keyframes shimmer { 0% { background-position: 100% 0; } 100% { background-position: 0 0; } }`}</style>
      </div>
    )
  }

  if (!project) {
    return (
      <div style={{ minHeight: '100%', background: S.bg, color: S.fg, fontFamily: "'Vazirmatn', system-ui, sans-serif", padding: 40 }} dir="rtl">
        <div style={{ maxWidth: 600, margin: '80px auto', textAlign: 'center', display: 'grid', gap: 16 }}>
          <h1 style={{ fontSize: '1.4rem', fontWeight: 900, margin: 0 }}>پروژه یافت نشد</h1>
          <p style={{ margin: 0, color: S.muted, fontWeight: 500 }}>پروژه مورد نظر وجود ندارد یا دسترسی ندارید.</p>
          <button type="button" style={{ padding: '12px 16px', fontWeight: 800, background: S.accent, border: '3px solid ' + S.border, boxShadow: '4px 4px 0 ' + S.border, cursor: 'pointer', color: S.fg, fontFamily: 'inherit', fontSize: 'inherit', justifySelf: 'center' }} onClick={() => navigate('/')}>← بازگشت به داشبورد</button>
        </div>
      </div>
    )
  }

  const activePrompts = prompts.filter(p => p.is_active)
  const archivedPrompts = prompts.filter(p => !p.is_active)

  return (
    <div style={{ minHeight: '100%', background: S.bg, color: S.fg, fontFamily: "'Vazirmatn', system-ui, sans-serif" }} dir="rtl">
      <div style={{ maxWidth: 1440, margin: '0 auto', padding: 20 }}>

        {/* ── Topbar ── */}
        <header style={{ position: 'sticky', top: 0, zIndex: 10, background: 'rgba(245,240,232,.92)', backdropFilter: 'blur(10px)', WebkitBackdropFilter: 'blur(10px)', border: '3px solid ' + S.border, boxShadow: S.shadow, padding: '14px 16px', display: 'flex', alignItems: 'center', gap: 14, justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontWeight: 900, cursor: 'pointer' }} onClick={() => navigate('/')}>
            <span style={{ width: 18, height: 18, background: S.accent, border: '3px solid ' + S.border, display: 'block', flexShrink: 0 }} />
            <span style={{ fontSize: '1.25rem', letterSpacing: '-0.03em' }}>FanoosAI</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <button type="button" style={{ padding: '11px 14px', fontWeight: 700, background: S.surface, border: '3px solid ' + S.border, cursor: 'pointer', color: S.fg, fontFamily: 'inherit', fontSize: 'inherit' }} onClick={() => navigate('/')}>← بازگشت</button>
            <div style={{ padding: '10px 14px', background: S.surface, border: '3px solid ' + S.border, fontWeight: 700 }}>{userName}</div>
            <button type="button" style={{ padding: '11px 14px', fontWeight: 700, background: S.surface, border: '3px solid ' + S.border, cursor: 'pointer', color: S.fg, fontFamily: 'inherit', fontSize: 'inherit' }} onClick={handleLogout}>خروج</button>
          </div>
        </header>

        {/* ── Project header ── */}
        <section style={{ padding: '22px 0 10px', display: 'grid', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
            <div style={{ display: 'grid', gap: 6 }}>
              <h1 style={{ margin: 0, fontSize: 'clamp(1.5rem, 3vw, 2.4rem)', fontWeight: 900, lineHeight: 1.1, letterSpacing: '-0.03em' }}>{project.name}</h1>
              {project.description && <p style={{ margin: 0, color: S.muted, fontWeight: 500, maxWidth: '62ch' }}>{project.description}</p>}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ padding: '6px 10px', border: '2px solid ' + S.border, background: '#fff', fontSize: '.8rem', fontWeight: 700 }}>ساخته شده: {relativeDate(project.created_at)}</span>
            {project.website_url && <span style={{ padding: '6px 10px', border: '2px solid ' + S.border, background: '#fff', fontSize: '.8rem', fontWeight: 700 }}>{project.website_url}</span>}
            <span style={{ padding: '6px 10px', border: '2px solid ' + S.border, background: activePrompts.length > 0 ? S.accent : '#fff', fontSize: '.8rem', fontWeight: 700 }}>{activePrompts.length} پرامپت فعال</span>
          </div>
        </section>

        {/* ── Actions ── */}
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 16, marginTop: 8 }}>
          <button type="button" style={{ padding: '12px 16px', fontWeight: 800, background: S.accent, border: '3px solid ' + S.border, boxShadow: '4px 4px 0 ' + S.border, cursor: 'pointer', color: S.fg, fontFamily: 'inherit', fontSize: 'inherit' }} onClick={() => { setShowForm(!showForm); setNewText(''); setSelectedModels([]) }}>
            {showForm ? 'انصراف' : '+ پرامپت جدید'}
          </button>
        </div>

        {/* ── Create prompt form ── */}
        {showForm && (
          <div style={{ background: S.surface, border: '3px solid ' + S.border, boxShadow: S.shadow, padding: 18, display: 'grid', gap: 14, marginBottom: 20 }}>
            <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 800 }}>پرامپت جدید</h3>
            <textarea
              placeholder="متن پرامپت را وارد کنید..."
              value={newText}
              onChange={e => setNewText(e.target.value)}
              rows={4}
              style={{ width: '100%', padding: 14, border: '3px solid ' + S.border, fontFamily: 'inherit', fontSize: 'inherit', fontWeight: 500, outline: 'none', resize: 'vertical' }}
            />
            {allModels.length > 0 && (
              <div style={{ display: 'grid', gap: 8 }}>
                <div style={{ fontWeight: 700, fontSize: '.9rem' }}>مدل‌های AI:</div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {allModels.map(m => (
                    <label key={m.id} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 10px', border: '2px solid ' + S.border, background: selectedModels.includes(m.id) ? S.accent : '#fff', cursor: 'pointer', fontSize: '.85rem', fontWeight: 600 }}>
                      <input type="checkbox" checked={selectedModels.includes(m.id)} onChange={() => setSelectedModels(prev => prev.includes(m.id) ? prev.filter(x => x !== m.id) : [...prev, m.id])} style={{ accentColor: S.border }} />
                      {m.name}
                    </label>
                  ))}
                </div>
              </div>
            )}
            <div style={{ display: 'flex', gap: 10 }}>
              <button type="button" disabled={!newText.trim() || creating} style={{ padding: '12px 16px', fontWeight: 800, background: S.accent, border: '3px solid ' + S.border, boxShadow: '4px 4px 0 ' + S.border, cursor: 'pointer', color: S.fg, fontFamily: 'inherit', fontSize: 'inherit', opacity: !newText.trim() || creating ? 0.5 : 1 }} onClick={handleCreate}>
                {creating ? 'در حال ساخت...' : 'ساخت پرامپت'}
              </button>
              <button type="button" style={{ padding: '11px 14px', fontWeight: 700, background: S.surface, border: '3px solid ' + S.border, cursor: 'pointer', color: S.fg, fontFamily: 'inherit', fontSize: 'inherit' }} onClick={() => setShowForm(false)}>لغو</button>
            </div>
          </div>
        )}

        {/* ── Loading ── */}
        {promptsLoading && (
          <div style={{ display: 'grid', gap: 16 }}>
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} style={{ padding: 18, height: 80, background: 'linear-gradient(90deg, #fff 25%, #f0ede7 37%, #fff 63%)', backgroundSize: '400% 100%', animation: 'shimmer 1.2s infinite', border: '3px solid ' + S.border, boxShadow: S.shadow }}>
                <div style={{ height: 16, width: '60%', marginBottom: 10, background: 'rgba(22,22,22,.12)' }} />
                <div style={{ height: 16, width: '40%', background: 'rgba(22,22,22,.12)' }} />
              </div>
            ))}
          </div>
        )}

        {/* ── Empty ── */}
        {!promptsLoading && prompts.length === 0 && (
          <div style={{ background: S.surface, border: '3px solid ' + S.border, boxShadow: S.shadow, padding: '36px 24px', textAlign: 'center', display: 'grid', placeItems: 'center', gap: 14 }}>
            <h2 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 900 }}>هنوز پرامپتی نداری</h2>
            <p style={{ margin: 0, color: S.muted, fontWeight: 500 }}>برای این پروژه پرامپتی ساخته نشده است.</p>
            <button type="button" style={{ padding: '12px 16px', fontWeight: 800, background: S.accent, border: '3px solid ' + S.border, boxShadow: '4px 4px 0 ' + S.border, cursor: 'pointer', color: S.fg, fontFamily: 'inherit', fontSize: 'inherit' }} onClick={() => setShowForm(true)}>+ پرامپت جدید</button>
          </div>
        )}

        {/* ── Active prompts ── */}
        {!promptsLoading && activePrompts.length > 0 && (
          <section style={{ display: 'grid', gap: 16 }}>
            <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 800, color: S.muted }}>فعال ({activePrompts.length})</h3>
            {activePrompts.map(prompt => (
              <PromptCard
                key={prompt.id}
                prompt={prompt}
                allModels={allModels}
                availableModels={availableModelsForPrompt(prompt)}
                addingModelFor={addingModelFor}
                runningId={runningId}
                onSetAddingModel={setAddingModelFor}
                onArchive={handleArchive}
                onAddModel={handleAddModel}
                onRemoveModel={handleRemoveModel}
                onRun={handleRun}
              />
            ))}
          </section>
        )}

        {/* ── Archived prompts ── */}
        {!promptsLoading && archivedPrompts.length > 0 && (
          <section style={{ display: 'grid', gap: 16, marginTop: 28 }}>
            <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 800, color: S.muted }}>آرشیو شده ({archivedPrompts.length})</h3>
            {archivedPrompts.map(prompt => (
              <div key={prompt.id} style={{ background: S.surface, border: '3px solid ' + S.border, boxShadow: S.shadow, padding: 18, display: 'grid', gap: 12, opacity: 0.55 }}>
                <p style={{ margin: 0, fontWeight: 500, lineHeight: 1.7, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{prompt.text}</p>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {prompt.models.map(m => (
                      <span key={m.id} style={{ padding: '4px 8px', border: '2px solid ' + S.border, background: '#eee', fontSize: '.75rem', fontWeight: 700 }}>{m.name}</span>
                    ))}
                  </div>
                  <span style={{ color: S.muted, fontSize: '.85rem', fontWeight: 500 }}>{relativeDate(prompt.created_at)}</span>
                </div>
              </div>
            ))}
          </section>
        )}

      </div>

      {/* ── Toast ── */}
      <div role="status" aria-live="polite" style={{ position: 'fixed', insetInlineStart: 20, bottom: 20, background: S.fg, color: '#fff', padding: '12px 14px', border: '3px solid ' + S.border, boxShadow: S.shadow, opacity: toast ? 1 : 0, transform: toast ? 'translateY(0)' : 'translateY(12px)', transition: 'opacity .2s, transform .2s', zIndex: 30, pointerEvents: toast ? 'auto' : 'none', fontWeight: 500 }}>
        {toast}
      </div>
    </div>
  )
}

/* ── PromptCard sub-component ── */

function PromptCard({
  prompt, allModels, availableModels, addingModelFor, runningId,
  onSetAddingModel, onArchive, onAddModel, onRemoveModel, onRun,
}: {
  prompt: PromptRead
  allModels: AIModelRead[]
  availableModels: AIModelRead[]
  addingModelFor: number | null
  runningId: number | null
  onSetAddingModel: (id: number | null) => void
  onArchive: (promptId: number) => void
  onAddModel: (promptId: number, modelId: number) => void
  onRemoveModel: (promptId: number, modelId: number) => void
  onRun: (promptId: number) => void
}) {
  const isRunning = runningId === prompt.id
  const isAdding = addingModelFor === prompt.id

  return (
    <div style={{ background: S.surface, border: '3px solid ' + S.border, boxShadow: S.shadow, padding: 18, display: 'grid', gap: 12 }}>
      <p style={{ margin: 0, fontWeight: 500, lineHeight: 1.7, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{prompt.text}</p>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
        {prompt.models.map(m => (
          <span key={m.id} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '4px 8px', border: '2px solid ' + S.border, background: S.accent, fontSize: '.75rem', fontWeight: 700 }}>
            {m.name}
            <button type="button" onClick={() => onRemoveModel(prompt.id, m.id)} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, color: S.fg, fontWeight: 900, fontSize: '.85rem', lineHeight: 1 }} title="حذف مدل">×</button>
          </span>
        ))}
        {allModels.length > 0 && (
          <div style={{ position: 'relative' }}>
            <button type="button" onClick={() => onSetAddingModel(isAdding ? null : prompt.id)} style={{ padding: '4px 8px', border: '2px dashed ' + S.border, background: 'transparent', fontSize: '.75rem', fontWeight: 700, cursor: 'pointer', color: S.muted, fontFamily: 'inherit' }}>
              + مدل
            </button>
            {isAdding && (
              <div style={{ position: 'absolute', top: '100%', right: 0, zIndex: 20, marginTop: 4, background: S.surface, border: '3px solid ' + S.border, boxShadow: S.shadow, padding: 8, minWidth: 180, display: 'grid', gap: 4 }}>
                {availableModels.length === 0 && <span style={{ fontSize: '.8rem', color: S.muted, padding: '4px 6px' }}>همه مدل‌ها انتخاب شده</span>}
                {availableModels.map(m => (
                  <button key={m.id} type="button" onClick={() => onAddModel(prompt.id, m.id)} style={{ textAlign: 'right', padding: '6px 8px', border: 'none', background: 'transparent', cursor: 'pointer', fontWeight: 600, fontSize: '.85rem', color: S.fg, fontFamily: 'inherit' }}>
                    {m.name} <span style={{ color: S.muted, fontWeight: 500 }}>({m.provider})</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <button type="button" disabled={isRunning || prompt.models.length === 0} style={{ padding: '8px 14px', fontWeight: 700, background: S.fg, color: '#fff', border: '3px solid ' + S.border, cursor: 'pointer', fontFamily: 'inherit', fontSize: '.85rem', opacity: isRunning || prompt.models.length === 0 ? 0.5 : 1 }} onClick={() => onRun(prompt.id)}>
            {isRunning ? 'در حال اجرا...' : '▶ اجرا'}
          </button>
          <button type="button" style={{ padding: '8px 14px', fontWeight: 700, background: S.surface, border: '3px solid ' + S.border, cursor: 'pointer', color: S.fg, fontFamily: 'inherit', fontSize: '.85rem' }} onClick={() => onArchive(prompt.id)}>
            بایگانی
          </button>
        </div>
        <span style={{ color: S.muted, fontSize: '.85rem', fontWeight: 500 }}>{relativeDate(prompt.created_at)}</span>
      </div>
    </div>
  )
}
