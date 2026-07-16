import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { listProjects, deleteProject, createProject, logout, type ProjectRead, type ProjectCreate } from '../lib/api'

const PERSIAN_DIGITS = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹']
function toPersianDigits(s: string | number) {
  return String(s).replace(/[0-9]/g, d => PERSIAN_DIGITS[+d])
}

function relativeDate(value: string) {
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

const S = {
  bg: '#f5f0e8',
  surface: '#ffffff',
  fg: '#161616',
  muted: '#66625d',
  border: '#161616',
  accent: '#c6ff40',
  shadow: '6px 6px 0 #161616',
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const [projects, setProjects] = useState<ProjectRead[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [sort, setSort] = useState('newest')
  const [toast, setToast] = useState('')
  const toastTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const [showCreate, setShowCreate] = useState(false)
  const [creating, setCreating] = useState(false)
  const [newProject, setNewProject] = useState<ProjectCreate>({ name: '', description: '', website_url: '' })

  const showToast = useCallback((msg: string) => {
    setToast(msg)
    clearTimeout(toastTimer.current)
    toastTimer.current = setTimeout(() => setToast(''), 2200)
  }, [])

  const fetchProjects = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listProjects()
      setProjects(data)
    } catch {
      setProjects([])
      showToast('دریافت پروژه‌ها از API ممکن نشد.')
    } finally {
      setLoading(false)
    }
  }, [showToast])

  useEffect(() => { fetchProjects() }, [fetchProjects])

  const handleCreateProject = async () => {
    if (!newProject.name.trim()) return
    setCreating(true)
    try {
      await createProject({
        name: newProject.name.trim(),
        description: newProject.description?.trim() || null,
        website_url: newProject.website_url?.trim() || null,
      })
      showToast('پروژه با موفقیت ساخته شد')
      setShowCreate(false)
      setNewProject({ name: '', description: '', website_url: '' })
      fetchProjects()
    } catch {
      showToast('خطا در ساخت پروژه')
    } finally {
      setCreating(false)
    }
  }

  const filtered = projects
    .filter(p => !search || p.name.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => {
      if (sort === 'newest') return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      if (sort === 'oldest') return new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
      if (sort === 'za') return (b.name || '').localeCompare(a.name || '', 'fa')
      return (a.name || '').localeCompare(b.name || '', 'fa')
    })

  const handleDelete = async (e: React.MouseEvent, project: ProjectRead) => {
    e.stopPropagation()
    const ok = window.confirm('پروژه «' + (project.name || 'بدون نام') + '» حذف شود؟')
    if (!ok) return
    try {
      await deleteProject(project.id)
      setProjects(prev => prev.filter(p => p.id !== project.id))
      showToast('پروژه با موفقیت حذف شد')
    } catch {
      showToast('خطا در حذف پروژه')
    }
  }

  const handleLogout = () => {
    void logout().finally(() => {
      localStorage.removeItem('user')
      navigate('/login')
    })
  }

  const userRaw = localStorage.getItem('user')
  let userName = 'کاربر'
  if (userRaw) {
    try {
      const u = JSON.parse(userRaw)
      userName = [u.first_name, u.last_name].filter(Boolean).join(' ') || u.phone || 'کاربر'
    } catch { /* ignore */ }
  }

  return (
    <div style={{ minHeight: '100%', background: S.bg, color: S.fg, fontFamily: "'Vazirmatn', system-ui, sans-serif" }} dir="rtl">
      <style>{`
        @keyframes shimmer {
          0% { background-position: 100% 0; }
          100% { background-position: 0 0; }
        }
        .dash-card:hover {
          transform: translate(-1px, -1px) !important;
        }
        .dash-del-btn:hover {
          transform: translate(-1px, -1px);
          box-shadow: 2px 2px 0 #161616;
        }
        .dash-grid { grid-template-columns: repeat(1, minmax(0, 1fr)); }
        @media (min-width: 768px) { .dash-grid { grid-template-columns: repeat(2, minmax(0, 1fr)) !important; } }
        @media (min-width: 1100px) { .dash-grid { grid-template-columns: repeat(3, minmax(0, 1fr)) !important; } }
        @media (min-width: 1360px) { .dash-grid { grid-template-columns: repeat(4, minmax(0, 1fr)) !important; } }
        @media (max-width: 820px) {
          .dash-topbar { flex-direction: column !important; align-items: stretch !important; }
          .dash-topbar-actions { width: 100% !important; justify-content: space-between !important; }
          .dash-toolbar { grid-template-columns: 1fr !important; }
          .dash-meta { flex-direction: column !important; align-items: stretch !important; }
          .dash-sort { width: 100% !important; }
        }
      `}</style>

      <div style={{ maxWidth: 1440, margin: '0 auto', padding: 20 }}>

        {/* ── Topbar ── */}
        <header
          className="dash-topbar"
          style={{
            position: 'sticky', top: 0, zIndex: 10,
            background: 'rgba(245,240,232,.92)',
            backdropFilter: 'blur(10px)',
            WebkitBackdropFilter: 'blur(10px)',
            border: '3px solid ' + S.border,
            boxShadow: S.shadow,
            padding: '14px 16px',
            display: 'flex',
            alignItems: 'center',
            gap: 14,
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontWeight: 900 }}>
            <span style={{ width: 18, height: 18, background: S.accent, border: '3px solid ' + S.border, display: 'block', flexShrink: 0 }} />
            <span style={{ fontSize: '1.25rem', letterSpacing: '-0.03em' }}>FanoosAI</span>
          </div>

          <div className="dash-topbar-actions" style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <button
              type="button"
              style={{
                padding: '12px 16px',
                fontWeight: 800,
                background: S.accent,
                border: '3px solid ' + S.border,
                boxShadow: '4px 4px 0 ' + S.border,
                cursor: 'pointer',
                color: S.fg,
                fontFamily: 'inherit',
                fontSize: 'inherit',
              }}
              onClick={() => setShowCreate(true)}
            >
              + پروژه جدید
            </button>

            <div style={{
              padding: '10px 14px',
              background: S.surface,
              border: '3px solid ' + S.border,
              fontWeight: 700,
            }}>
              {userName}
            </div>

            <button
              type="button"
              style={{
                padding: '11px 14px',
                fontWeight: 700,
                background: S.surface,
                border: '3px solid ' + S.border,
                cursor: 'pointer',
                color: S.fg,
                fontFamily: 'inherit',
                fontSize: 'inherit',
              }}
              onClick={handleLogout}
            >
              خروج
            </button>
          </div>
        </header>

        {/* ── Hero ── */}
        <section style={{ padding: '22px 0 10px', display: 'grid', gap: 12 }}>
          <h1 style={{
            margin: 0,
            fontSize: 'clamp(1.8rem, 4vw, 3.4rem)',
            lineHeight: 1.1,
            letterSpacing: '-0.04em',
            fontWeight: 900,
          }}>
            پروژه‌هایت را مدیریت کن
          </h1>
          <p style={{ margin: 0, color: S.muted, maxWidth: '62ch', fontWeight: 500, fontSize: '1rem' }}>
            همه پروژه‌ها در یک نگاه، با جستجو، مرتب‌سازی، حذف سریع و وضعیت‌های خالی یا درحال بارگذاری.
          </p>

          {/* Toolbar */}
          <div className="dash-toolbar" style={{
            display: 'grid',
            gridTemplateColumns: '1fr auto',
            gap: 12,
            marginTop: 10,
          }}>
            <label style={{ position: 'relative' }}>
              <span style={{
                position: 'absolute',
                insetInlineEnd: 'auto',
                insetInlineStart: 16,
                top: '50%',
                transform: 'translateY(-50%)',
                fontSize: '1rem',
                color: S.muted,
                pointerEvents: 'none',
                userSelect: 'none',
              }} aria-hidden="true">⌕</span>
              <span style={{ position: 'absolute', width: 1, height: 1, padding: 0, margin: -1, overflow: 'hidden', clip: 'rect(0,0,0,0)', whiteSpace: 'nowrap', border: 0 }}>
                جستجوی پروژه
              </span>
              <input
                type="search"
                placeholder="جستجو بر اساس نام پروژه"
                value={search}
                onChange={e => setSearch(e.target.value)}
                style={{
                  width: '100%',
                  padding: '14px 16px',
                  paddingInlineStart: 48,
                  border: '3px solid ' + S.border,
                  background: S.surface,
                  color: S.fg,
                  fontFamily: 'inherit',
                  fontSize: 'inherit',
                  fontWeight: 500,
                  outline: 'none',
                }}
              />
            </label>

            <select
              className="dash-sort"
              aria-label="مرتب‌سازی پروژه‌ها"
              value={sort}
              onChange={e => setSort(e.target.value)}
              style={{
                padding: '0 14px',
                minWidth: 220,
                border: '3px solid ' + S.border,
                background: S.surface,
                color: S.fg,
                fontFamily: 'inherit',
                fontSize: 'inherit',
                fontWeight: 500,
                outline: 'none',
              }}
            >
              <option value="newest">جدیدترین</option>
              <option value="oldest">قدیمی‌ترین</option>
              <option value="az">الفبایی: الف تا ی</option>
              <option value="za">الفبایی: ی تا الف</option>
            </select>
          </div>

          {/* Meta row */}
          <div className="dash-meta" style={{
            marginTop: 10,
            display: 'flex',
            gap: 10,
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}>
            <div style={{ fontWeight: 800 }}>{toPersianDigits(filtered.length)} پروژه</div>
            <div style={{ color: S.muted, fontWeight: 500 }}>
              {loading ? 'در حال بارگذاری…' : (filtered.length ? 'داده‌ها به‌روز هستند' : 'موردی برای نمایش نیست')}
            </div>
          </div>
        </section>

        {/* ── Loading skeletons ── */}
        {loading && (
          <div style={{
            display: 'grid',
            gap: 16,
            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          }} aria-live="polite">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                style={{
                  padding: 18,
                  height: 210,
                  background: 'linear-gradient(90deg, #fff 25%, #f0ede7 37%, #fff 63%)',
                  backgroundSize: '400% 100%',
                  animation: 'shimmer 1.2s infinite',
                  border: '3px solid ' + S.border,
                  boxShadow: S.shadow,
                }}
              >
                <div style={{ height: 24, width: '70%', marginBottom: 12, background: 'rgba(22,22,22,.12)' }} />
                <div style={{ height: 16, width: '92%', marginBottom: 12, background: 'rgba(22,22,22,.12)' }} />
                <div style={{ height: 16, width: '85%', marginBottom: 12, background: 'rgba(22,22,22,.12)' }} />
                <div style={{ height: 16, width: '40%', background: 'rgba(22,22,22,.12)' }} />
              </div>
            ))}
          </div>
        )}

        {/* ── Empty state ── */}
        {!loading && filtered.length === 0 && (
          <div style={{
            background: S.surface,
            border: '3px solid ' + S.border,
            boxShadow: S.shadow,
            padding: '36px 24px',
            textAlign: 'center',
            display: 'grid',
            placeItems: 'center',
            gap: 14,
          }}>
            <img
              src="https://placehold.co/240x160/png?text=%D9%86%D8%A8%D9%88%D8%AF+%D9%BE%D8%B1%D9%88%DA%98%D9%87"
              alt="تصویر حالت خالی"
              style={{ width: 'min(240px, 60vw)', height: 'auto' }}
            />
            <h2 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 900 }}>هنوز پروژه‌ای نداری</h2>
            <p style={{ margin: 0, color: S.muted, fontWeight: 500 }}>با ساخت پروژه جدید، داشبوردت همین‌جا پر می‌شود.</p>
            <button
              type="button"
              style={{
                padding: '12px 16px',
                fontWeight: 800,
                background: S.accent,
                border: '3px solid ' + S.border,
                boxShadow: '4px 4px 0 ' + S.border,
                cursor: 'pointer',
                color: S.fg,
                fontFamily: 'inherit',
                fontSize: 'inherit',
              }}
              onClick={() => setShowCreate(true)}
            >
              + پروژه جدید
            </button>
          </div>
        )}

        {/* ── Projects grid ── */}
        {!loading && filtered.length > 0 && (
          <section className="dash-grid" style={{
            display: 'grid',
            gap: 16,
            marginTop: 18,
          }} aria-live="polite">
            {filtered.map(project => (
              <article
                key={project.id}
                className="dash-card"
                tabIndex={0}
                onClick={e => {
                  if ((e.target as HTMLElement).closest('.dash-del-btn')) return
                  if ((e.target as HTMLElement).closest('.dash-detail-link')) return
                  navigate('/projects/' + project.id)
                }}
                onKeyDown={e => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    navigate('/projects/' + project.id)
                  }
                }}
                style={{
                  background: S.surface,
                  border: '3px solid ' + S.border,
                  boxShadow: S.shadow,
                  padding: 18,
                  display: 'grid',
                  gap: 14,
                  minHeight: 210,
                  position: 'relative',
                  cursor: 'pointer',
                  transition: 'transform .1s',
                }}
              >
                <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start', justifyContent: 'space-between' }}>
                  <h2 style={{
                    margin: 0,
                    fontSize: '1.2rem',
                    lineHeight: 1.35,
                    fontWeight: 900,
                  }}>
                    {project.name || 'پروژه بدون نام'}
                  </h2>
                  <button
                    type="button"
                    className="dash-del-btn"
                    aria-label={'حذف پروژه ' + (project.name || '')}
                    onClick={e => handleDelete(e, project)}
                    style={{
                      width: 40,
                      height: 40,
                      display: 'grid',
                      placeItems: 'center',
                      cursor: 'pointer',
                      background: '#fff',
                      flex: '0 0 auto',
                      border: '3px solid ' + S.border,
                      color: S.fg,
                      fontFamily: 'inherit',
                      fontSize: 'inherit',
                      padding: 0,
                    }}
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="3 6 5 6 21 6" />
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                    </svg>
                  </button>
                </div>

                <p style={{
                  margin: 0,
                  color: S.muted,
                  display: '-webkit-box',
                  WebkitLineClamp: 2,
                  WebkitBoxOrient: 'vertical',
                  overflow: 'hidden',
                  minHeight: '3.1em',
                  fontWeight: 500,
                }}>
                  {project.description || 'بدون توضیح'}
                </p>

                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: 10,
                  marginTop: 'auto',
                }}>
                  <div style={{
                    display: 'flex',
                    gap: 8,
                    flexWrap: 'wrap',
                    color: S.muted,
                    fontSize: '.92rem',
                  }}>
                    <span style={{
                      padding: '6px 10px',
                      border: '2px solid ' + S.border,
                      background: '#fff',
                      fontSize: '.8rem',
                      fontWeight: 700,
                    }}>
                      ساخته شده: {relativeDate(project.created_at)}
                    </span>
                  </div>
                  <span
                    className="dash-detail-link"
                    style={{ fontWeight: 800, cursor: 'pointer' }}
                    onClick={e => {
                      e.stopPropagation()
                      navigate('/projects/' + project.id)
                    }}
                  >
                    جزئیات ←
                  </span>
                </div>
              </article>
            ))}
          </section>
        )}



      </div>

      {/* ── Create project modal ── */}
      {showCreate && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 40, background: 'rgba(0,0,0,.3)', display: 'grid', placeItems: 'center', padding: 20 }} onClick={() => setShowCreate(false)}>
          <div style={{ background: S.surface, border: '3px solid ' + S.border, boxShadow: S.shadow, padding: 24, width: '100%', maxWidth: 460, display: 'grid', gap: 16 }} onClick={e => e.stopPropagation()}>
            <h2 style={{ margin: 0, fontSize: '1.3rem', fontWeight: 900 }}>پروژه جدید</h2>
            <div style={{ display: 'grid', gap: 6 }}>
              <label style={{ fontWeight: 700, fontSize: '.9rem' }}>نام پروژه</label>
              <input type="text" placeholder="مثال: فروشگاه آنلاین" value={newProject.name} onChange={e => setNewProject(p => ({ ...p, name: e.target.value }))} style={{ width: '100%', padding: 14, border: '3px solid ' + S.border, fontFamily: 'inherit', fontSize: 'inherit', fontWeight: 500, outline: 'none' }} />
            </div>
            <div style={{ display: 'grid', gap: 6 }}>
              <label style={{ fontWeight: 700, fontSize: '.9rem' }}>توضیحات <span style={{ color: S.muted, fontWeight: 500 }}>(اختیاری)</span></label>
              <textarea placeholder="توضیح کوتاهی درباره پروژه..." value={newProject.description || ''} onChange={e => setNewProject(p => ({ ...p, description: e.target.value }))} rows={3} style={{ width: '100%', padding: 14, border: '3px solid ' + S.border, fontFamily: 'inherit', fontSize: 'inherit', fontWeight: 500, outline: 'none', resize: 'vertical' }} />
            </div>
            <div style={{ display: 'grid', gap: 6 }}>
              <label style={{ fontWeight: 700, fontSize: '.9rem' }}>آدرس وب‌سایت <span style={{ color: S.muted, fontWeight: 500 }}>(اختیاری)</span></label>
              <input type="url" placeholder="https://example.com" value={newProject.website_url || ''} onChange={e => setNewProject(p => ({ ...p, website_url: e.target.value }))} style={{ width: '100%', padding: 14, border: '3px solid ' + S.border, fontFamily: 'inherit', fontSize: 'inherit', fontWeight: 500, outline: 'none' }} />
            </div>
            <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
              <button type="button" disabled={!newProject.name.trim() || creating} style={{ padding: '12px 16px', fontWeight: 800, background: S.accent, border: '3px solid ' + S.border, boxShadow: '4px 4px 0 ' + S.border, cursor: 'pointer', color: S.fg, fontFamily: 'inherit', fontSize: 'inherit', opacity: !newProject.name.trim() || creating ? 0.5 : 1 }} onClick={handleCreateProject}>
                {creating ? 'در حال ساخت...' : 'ساخت پروژه'}
              </button>
              <button type="button" style={{ padding: '11px 14px', fontWeight: 700, background: S.surface, border: '3px solid ' + S.border, cursor: 'pointer', color: S.fg, fontFamily: 'inherit', fontSize: 'inherit' }} onClick={() => setShowCreate(false)}>انصراف</button>
            </div>
          </div>
        </div>
      )}

      {/* ── Toast ── */}
      <div
        role="status"
        aria-live="polite"
        style={{
          position: 'fixed',
          insetInlineStart: 20,
          bottom: 20,
          background: S.fg,
          color: '#fff',
          padding: '12px 14px',
          border: '3px solid ' + S.border,
          boxShadow: S.shadow,
          opacity: toast ? 1 : 0,
          transform: toast ? 'translateY(0)' : 'translateY(12px)',
          transition: 'opacity .2s, transform .2s',
          zIndex: 30,
          pointerEvents: toast ? 'auto' : 'none',
          fontWeight: 500,
        }}
      >
        {toast}
      </div>
    </div>
  )
}
