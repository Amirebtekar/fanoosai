import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from '@tanstack/react-router'
import { addAlertRule, addProjectBrand, createReportShare, deleteProjectBrand, exportRunsCsv, getModelPerformance, getProjectDashboard, getReportShareUrl, listAlerts, listObservedBrands, listProjectBrands, readAlert, revokeReportShare, type AlertItem, type ModelPerformance, type ObservedBrand, type ProjectBrand, type ProjectDashboard } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { PromptManagement } from './prompt-management'
import { toast } from 'sonner'

export function ProjectManagementPage() {
  const { id } = useParams({ from: '/_authenticated/projects_/$id_/manage' })
  const navigate = useNavigate()
  useEffect(() => { void navigate({ to: '/projects/' + id, replace: true }) }, [id, navigate])
  return null
}

export function ProjectManagementSections({ projectId }: { projectId: number }) {
  return <>
    <section className="mb-8 border-r-4 border-primary bg-card p-4" aria-labelledby="management-help">
      <div className="flex items-center gap-2">
        <h2 id="management-help" className="font-black">این صفحه برای چیست؟</h2>
        <Tooltip><TooltipTrigger asChild><Button variant="ghost" size="sm">راهنما</Button></TooltipTrigger><TooltipContent side="bottom">برندها، شاخص‌ها، هشدارها و گزارش‌های پروژه در اینجا هستند.</TooltipContent></Tooltip>
      </div>
      <p className="mt-2 text-sm leading-6 text-muted-text">برای ثبت رقیب، بررسی شاخص‌ها، ساخت هشدار و دریافت گزارش از این صفحه استفاده کنید.</p>
    </section>
    <PromptManagement projectId={projectId} />
    <CompetitorSettings projectId={projectId} />
    <ProjectKpis projectId={projectId} />
    <ModelPerformanceTable projectId={projectId} />
    <AlertInbox projectId={projectId} />
    <ReportActions projectId={projectId} />
  </>
}

function CompetitorSettings({ projectId }: { projectId: number }) {
  const [competitors, setCompetitors] = useState<ProjectBrand[]>([])
  const [observedBrands, setObservedBrands] = useState<ObservedBrand[]>([])
  const [selectedBrandId, setSelectedBrandId] = useState('')
  const load = useCallback(() => Promise.all([listProjectBrands(projectId), listObservedBrands(projectId)]).then(([brands, observed]) => { setCompetitors(brands.filter(brand => brand.kind === 'competitor')); setObservedBrands(observed) }).catch(() => toast.error('خطا در دریافت برندها')), [projectId])
  useEffect(() => { void load() }, [load])
  const availableBrands = observedBrands.filter(brand => !competitors.some(competitor => competitor.domain === brand.domain))
  const add = async () => { const brand = availableBrands.find(item => item.brand_id === Number(selectedBrandId)); if (!brand) return; await addProjectBrand(projectId, { name: brand.name, domain: brand.domain, kind: 'competitor' }); setSelectedBrandId(''); load() }
  return <Card className="mb-8 border-border shadow-[6px_6px_0_var(--color-shadow)]"><CardHeader><h2 className="text-lg font-black">رقبا</h2></CardHeader><CardContent className="space-y-3">
    <p className="text-sm text-muted-text">از برندهای شناسایی‌شده در اجرای این پروژه انتخاب کنید.</p>
    <div className="flex flex-wrap gap-2"><select value={selectedBrandId} onChange={e => setSelectedBrandId(e.target.value)} aria-label="برند شناسایی‌شده" className="min-w-56 border-2 border-border bg-card p-2"><option value="">انتخاب برند</option>{availableBrands.map(brand => <option key={brand.brand_id} value={brand.brand_id}>{brand.name} ({brand.domain})</option>)}</select><Button onClick={add} disabled={!selectedBrandId}>افزودن</Button></div>
    {!availableBrands.length && <p className="text-sm text-muted-text">برند جدیدی برای انتخاب وجود ندارد.</p>}
    {competitors.map(brand => <div key={brand.id} className="flex justify-between border-2 border-border p-2"><span>{brand.name} {brand.domain && `(${brand.domain})`}</span><button onClick={() => deleteProjectBrand(projectId, brand.id).then(load)} aria-label={`حذف ${brand.name}`}>×</button></div>)}
  </CardContent></Card>
}

function ProjectKpis({ projectId }: { projectId: number }) {
  const [data, setData] = useState<ProjectDashboard | null>(null)
  const [error, setError] = useState(false)
  useEffect(() => { getProjectDashboard(projectId).then(setData).catch(() => setError(true)) }, [projectId])
  if (error) return <p className="mb-6 text-sm text-red-600">دریافت شاخص‌ها ممکن نشد.</p>
  if (!data) return <Skeleton className="mb-6 h-24 w-full bg-accent" />
  return <Card className="mb-8 border-border shadow-[6px_6px_0_var(--color-shadow)]"><CardHeader><h2 className="text-lg font-black">شاخص‌های پروژه</h2></CardHeader><CardContent className="space-y-3"><div className="grid grid-cols-3 gap-2 text-center"><div>نمایش‌پذیری<br /><b>{data.visibility}%</b></div><div>میانگین رتبه<br /><b>{data.average_rank?.toFixed(1) ?? '—'}</b></div><div>حضور<br /><b>{data.appearances}</b></div></div><p className="text-sm text-muted-text">آخرین اجرای موفق: {data.last_successful_run ? new Date(data.last_successful_run).toLocaleString('fa-IR') : '—'}</p>{data.competitors.map(item => <p key={item.name} className="border-t pt-2 text-sm">{item.name}: رتبه {item.average_rank?.toFixed(1) ?? '—'}، {item.appearances} حضور</p>)}</CardContent></Card>
}

function ModelPerformanceTable({ projectId }: { projectId: number }) {
  const [models, setModels] = useState<ModelPerformance[] | null>(null)
  const [error, setError] = useState(false)
  useEffect(() => { getModelPerformance(projectId).then(setModels).catch(() => setError(true)) }, [projectId])
  if (error) return <p className="mb-6 text-sm text-red-600">دریافت عملکرد مدل‌ها ممکن نشد.</p>
  if (!models) return <Skeleton className="mb-6 h-48 w-full bg-accent" />
  return <Card className="mb-8 border-border shadow-[6px_6px_0_var(--color-shadow)]"><CardHeader><h2 className="text-lg font-black">عملکرد مدل‌ها</h2></CardHeader><CardContent><ModelPerformanceTableContent models={models} /></CardContent></Card>
}

export function ModelPerformanceTableContent({ models }: { models: ModelPerformance[] }) {
  if (!models.length) return <p className="text-sm text-muted-text">هنوز اجرایی برای مدل‌ها ثبت نشده است.</p>
  return <div className="overflow-x-auto"><table className="w-full min-w-[720px] text-right text-sm">
    <thead className="border-b-2 border-border text-muted-text"><tr>
      <th className="p-2" scope="col">مدل</th>
      <th className="p-2" scope="col">کل درخواست‌ها</th>
      <th className="p-2 text-emerald-700" scope="col">موفق مستقیم</th>
      <th className="p-2 text-amber-700" scope="col">موفق با AvalAI</th>
      <th className="p-2 text-red-600" scope="col">ناموفق نهایی</th>
      <th className="p-2" scope="col">نرخ موفقیت</th>
    </tr></thead>
    <tbody>{models.map(model => <tr key={model.ai_model} className="border-b border-border/60">
      <td className="p-2 font-bold">{model.ai_model}</td>
      <td className="p-2">{model.total_runs.toLocaleString('fa-IR')}</td>
      <td className="p-2 font-bold text-emerald-700">{model.direct_successful_runs.toLocaleString('fa-IR')}</td>
      <td className="p-2 font-bold text-amber-700">{model.fallback_successful_runs.toLocaleString('fa-IR')}</td>
      <td className="p-2 font-bold text-red-600">{model.failed_runs.toLocaleString('fa-IR')}</td>
      <td className="p-2">{model.success_rate.toLocaleString('fa-IR')}٪</td>
    </tr>)}</tbody>
  </table></div>
}

function AlertInbox({ projectId }: { projectId: number }) {
  const [alerts, setAlerts] = useState<AlertItem[]>([])
  const load = useCallback(() => listAlerts(projectId).then(setAlerts), [projectId])
  useEffect(() => { void load() }, [load])
  const kinds = [['rank_drop', 'افت رتبه'], ['disappearance', 'ناپدید شدن'], ['new_competitor', 'رقیب جدید'], ['run_failure', 'خطای اجرا']]
  return <Card className="mb-8 border-border"><CardHeader><h2 className="text-lg font-black">هشدارها</h2></CardHeader><CardContent className="space-y-2"><p className="text-sm text-muted-text">قاعده‌ای بسازید تا تغییرهای مهم پروژه را از دست ندهید.</p><div className="flex flex-wrap gap-2">{kinds.map(([kind, label]) => <Button key={kind} size="sm" variant="outline" onClick={() => addAlertRule(projectId, kind).then(() => toast.success('قانون هشدار اضافه شد'))}>{label}</Button>)}</div>{alerts.length ? alerts.map(alert => <button key={alert.id} className="block w-full border-2 border-border p-2 text-right" onClick={() => readAlert(projectId, alert.id).then(load)}>{alert.message}</button>) : <p className="text-sm text-muted-text">هشداری ندارید.</p>}</CardContent></Card>
}

function ReportActions({ projectId }: { projectId: number }) {
  const [share, setShare] = useState<{ token: string; expiresAt: string } | null>(null)
  const [isCreating, setIsCreating] = useState(false)
  const shareUrl = share && getReportShareUrl(share.token)

  const createShare = async () => {
    setIsCreating(true)
    try {
      const result = await createReportShare(projectId)
      setShare({ token: result.token, expiresAt: result.expires_at })
      toast.success('لینک خصوصی ساخته شد')
    } catch {
      toast.error('ساخت لینک خصوصی ممکن نشد')
    } finally {
      setIsCreating(false)
    }
  }

  const copyShareUrl = async () => {
    if (!shareUrl || !navigator.clipboard) return toast.error('لینک را دستی کپی کنید')
    try {
      await navigator.clipboard.writeText(shareUrl)
      toast.success('لینک کپی شد')
    } catch {
      toast.error('لینک را دستی کپی کنید')
    }
  }

  const revokeShare = async () => {
    if (!share) return
    try {
      await revokeReportShare(projectId, share.token)
      setShare(null)
      toast.success('لینک لغو شد')
    } catch {
      toast.error('لغو لینک ممکن نشد')
    }
  }

  return <Card className="mb-8 border-border"><CardHeader><h2 className="text-lg font-black">گزارش</h2></CardHeader><CardContent className="space-y-3"><p className="text-sm text-muted-text">خروجی اجراها را دریافت کنید یا یک لینک خصوصیِ گزارش بسازید.</p><div className="flex flex-wrap gap-2"><Button variant="outline" onClick={() => exportRunsCsv(projectId)}>دانلود CSV</Button><Button onClick={createShare} disabled={isCreating}>{isCreating ? 'در حال ساخت…' : 'ساخت لینک خصوصی'}</Button></div>{shareUrl && <div className="space-y-2 border-t border-border pt-3" aria-live="polite"><label htmlFor="report-share-url" className="text-sm font-bold">لینک اشتراک‌گذاری</label><div className="flex flex-col gap-2 sm:flex-row"><Input id="report-share-url" value={shareUrl} readOnly dir="ltr" aria-label="لینک خصوصی گزارش" /><Button variant="outline" onClick={copyShareUrl}>کپی</Button></div><p className="text-sm text-muted-text">اعتبار تا {new Date(share.expiresAt).toLocaleString('fa-IR')}</p><div className="flex flex-wrap gap-2"><Button variant="outline" asChild><a href={shareUrl} target="_blank" rel="noreferrer">باز کردن لینک</a></Button><Button variant="outline" onClick={revokeShare}>لغو دسترسی</Button></div></div>}</CardContent></Card>
}
