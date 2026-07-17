import { useState, useEffect } from 'react'
import { BarChart3 } from 'lucide-react'
import { listProjects, listPrompts, getPromptRankings, type ProjectRead, type PromptRead, type PromptRankingItem } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'

const RANK_BG: Record<number, string> = { 1: '#ef4444', 2: '#dc2626', 3: '#b91c1c' }

export function AnalyticsPage() {
  const [projects, setProjects] = useState<ProjectRead[]>([])
  const [prompts, setPrompts] = useState<PromptRead[]>([])
  const [selectedProject, setSelectedProject] = useState('')
  const [selectedPrompt, setSelectedPrompt] = useState('')
  const [rankings, setRankings] = useState<PromptRankingItem[]>([])
  const [loading, setLoading] = useState(true)
  const [loadingRankings, setLoadingRankings] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true)
    listProjects()
      .then(setProjects)
      .catch(() => setError('دریافت پروژه‌ها ممکن نشد'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!selectedProject) { setPrompts([]); return }
    listPrompts(Number(selectedProject))
      .then(setPrompts)
      .catch(() => setError('دریافت پرامپت‌ها ممکن نشد'))
  }, [selectedProject])

  useEffect(() => {
    if (!selectedPrompt) { setRankings([]); return }
    setLoadingRankings(true)
    getPromptRankings(Number(selectedPrompt))
      .then(setRankings)
      .catch(() => setError('دریافت آنالیز ممکن نشد'))
      .finally(() => setLoadingRankings(false))
  }, [selectedPrompt])

  const groupedRankings = rankings.reduce<Record<string, PromptRankingItem[]>>((acc, item) => {
    if (!acc[item.ai_model]) acc[item.ai_model] = []
    acc[item.ai_model].push(item)
    return acc
  }, {})

  return (
    <div className="min-h-full bg-bg font-vazirmatn" dir="rtl">
      <Header fixed className="bg-bg">
        <h1 className="text-lg font-black">آنالیز برند</h1>
      </Header>
      <Main fixed>
        <p className="mb-6 text-sm font-medium text-muted-text">پرامپت مورد نظر را انتخاب کنید تا رتبه برندها را مشاهده کنید.</p>

        <div className="mb-6 flex flex-col gap-3 sm:flex-row">
          <Select value={selectedProject} onValueChange={v => { setSelectedProject(v); setSelectedPrompt(''); setRankings([]) }}>
            <SelectTrigger className="w-full border-border font-medium sm:w-[280px]">
              <SelectValue placeholder="انتخاب پروژه..." />
            </SelectTrigger>
            <SelectContent>
              {projects.map(p => <SelectItem key={p.id} value={String(p.id)}>{p.name}</SelectItem>)}
            </SelectContent>
          </Select>

          <Select value={selectedPrompt} onValueChange={setSelectedPrompt} disabled={!selectedProject}>
            <SelectTrigger className="w-full border-border font-medium sm:w-[320px]">
              <SelectValue placeholder="انتخاب پرامپت..." />
            </SelectTrigger>
            <SelectContent>
              {prompts.map(p => <SelectItem key={p.id} value={String(p.id)}>{p.text.slice(0, 60)}{p.text.length > 60 ? '...' : ''}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>

        {error && <div className="mb-4 border-3 border-red-500 bg-red-50 p-3 text-sm font-bold text-red-700">{error}</div>}

        {loading && <div className="space-y-4">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-32 w-full bg-accent" />)}</div>}

        {loadingRankings && <div className="space-y-4">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-32 w-full bg-accent" />)}</div>}

        {!loadingRankings && !selectedPrompt && !loading && (
          <div className="flex flex-col items-center gap-4 rounded-none border-3 border-border bg-card p-10 text-center shadow-[6px_6px_0_var(--color-shadow)]">
            <BarChart3 className="size-10 text-muted-text" />
            <h2 className="text-xl font-black">یک پروژه و پرامپت انتخاب کنید</h2>
            <p className="text-sm font-medium text-muted-text">ابتدا پروژه و سپس پرامپت مورد نظر را انتخاب کنید تا رتبه برندها نمایش داده شود.</p>
          </div>
        )}

        {!loadingRankings && selectedPrompt && Object.keys(groupedRankings).length === 0 && (
          <div className="flex flex-col items-center gap-4 rounded-none border-3 border-border bg-card p-10 text-center shadow-[6px_6px_0_var(--color-shadow)]">
            <h2 className="text-xl font-black">داده‌ای وجود ندارد</h2>
            <p className="text-sm font-medium text-muted-text">برای این پرامپت هنوز رتبه‌ای ثبت نشده است.</p>
          </div>
        )}

        {!loadingRankings && Object.keys(groupedRankings).length > 0 && (
          <div className="space-y-6">
            {Object.entries(groupedRankings).map(([model, items]) => (
              <Card key={model} className="border-border shadow-[6px_6px_0_var(--color-shadow)]">
                <CardHeader>
                  <CardTitle className="text-lg font-black">{model}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {items.sort((a, b) => a.rank - b.rank).map(item => {
                    const maxRank = Math.max(...items.map(i => i.rank), 1)
                    const barWidth = `${(1 - (item.rank - 1) / maxRank) * 100}%`
                    return (
                      <div key={item.brand + item.ai_model} className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span
                            className="inline-block border-2 border-border px-2 py-0.5 text-xs font-bold"
                            style={{ background: RANK_BG[item.rank] || '#999590', color: '#161616' }}
                          >
                            #{item.rank}
                          </span>
                          <span className="text-sm font-bold">{item.brand}</span>
                          {item.domain && <span className="text-xs text-muted-text">{item.domain}</span>}
                        </div>
                        <div className="h-2.5 w-full border-2 border-border bg-[#e0ddd5]">
                          <div className="h-full border-l-2 border-border bg-accent-neon transition-all duration-300" style={{ width: barWidth }} />
                        </div>
                      </div>
                    )
                  })}
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </Main>
    </div>
  )
}
