import { useCallback, useEffect, useState } from 'react'
import { getAdminCosts, getAdminOverview, getErrorMessage, getExtractionSettings, listAdminBrands, listAdminModels, listAdminPrompts, listAdminReferences, mergeAdminBrands, previewAdminBrandMerge, resetExtractionSettings, saveModelSelection, setAdminPromptActive, syncGatewayModels, updateExtractionSettings, type AdminBrand, type AdminCostItem, type AdminOverview, type AdminPromptRead, type AdminReference, type AIModelRead, type BrandMergePreview, type ExtractionSettings, type GatewayModel } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { AlertDialog, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog'
import { Switch } from '@/components/ui/switch'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { toast } from 'sonner'

export function AdminPanelPage() {
  return (
    <div className="min-h-full bg-bg font-vazirmatn" dir="rtl">
      <Header fixed className="bg-bg"><h1 className="text-lg font-black">پنل ادمین</h1></Header>
      <Main fixed>
        <AdminPanel />
      </Main>
    </div>
  )
}

function AdminPanel() {
  const [overview, setOverview] = useState<AdminOverview | null>(null)
  const loadOverview = useCallback(() => {
    getAdminOverview().then(setOverview).catch(e => toast.error(getErrorMessage(e, 'خطا در دریافت آمار')))
  }, [])
  useEffect(() => { loadOverview() }, [loadOverview])

  return (
    <div className="space-y-8">
      {overview ? <StatsCards overview={overview} /> : <div className="grid grid-cols-2 gap-4 md:grid-cols-4">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24 bg-accent" />)}</div>}

      <Tabs defaultValue="models" className="w-full">
        <TabsList className="h-auto w-full justify-start gap-1 rounded-none border-2 border-border bg-card p-1">
          <TabsTrigger value="models" className="rounded-none border-2 border-transparent font-bold data-[state=active]:border-border">مدل‌ها</TabsTrigger>
          <TabsTrigger value="prompts" className="rounded-none border-2 border-transparent font-bold data-[state=active]:border-border">پرامپت‌ها</TabsTrigger>
          <TabsTrigger value="extraction" className="rounded-none border-2 border-transparent font-bold data-[state=active]:border-border">تنظیمات استخراج</TabsTrigger>
          <TabsTrigger value="references" className="rounded-none border-2 border-transparent font-bold data-[state=active]:border-border">رفرنس‌ها</TabsTrigger>
          <TabsTrigger value="brands" className="rounded-none border-2 border-transparent font-bold data-[state=active]:border-border">برندها</TabsTrigger>
          <TabsTrigger value="costs" className="rounded-none border-2 border-transparent font-bold data-[state=active]:border-border">هزینه‌ها</TabsTrigger>
        </TabsList>
        <TabsContent value="models"><ModelsTab onLoaded={loadOverview} /></TabsContent>
        <TabsContent value="prompts"><PromptsTab onLoaded={loadOverview} /></TabsContent>
        <TabsContent value="extraction"><ExtractionTab /></TabsContent>
        <TabsContent value="references"><ReferencesTab /></TabsContent>
        <TabsContent value="brands"><BrandsTab /></TabsContent>
        <TabsContent value="costs"><CostsTab /></TabsContent>
      </Tabs>
    </div>
  )
}

function StatsCards({ overview }: { overview: AdminOverview }) {
  const stats = [
    { label: 'کاربران', value: overview.users },
    { label: 'پروژه‌ها', value: overview.projects },
    { label: 'پرامپت فعال', value: overview.prompts_active },
    { label: 'پرامپت بایگانی', value: overview.prompts_archived },
    { label: 'مدل فعال', value: overview.models_active },
    { label: 'مدل غیرفعال', value: overview.models_inactive },
    { label: 'کل اجراها', value: overview.runs_total },
    { label: 'اجراهای ناموفق', value: overview.runs_failed },
  ]
  return (
    <section aria-label="آمار کلی" className="grid grid-cols-2 gap-4 md:grid-cols-4">
      {stats.map(stat => (
        <div key={stat.label} className="border-2 border-border bg-card p-4 shadow-[4px_4px_0_var(--color-shadow)]">
          <p className="text-sm font-bold text-muted-text">{stat.label}</p>
          <p className="mt-1 text-2xl font-black">{stat.value.toLocaleString('fa-IR')}</p>
        </div>
      ))}
    </section>
  )
}

function ModelsTab({ onLoaded }: { onLoaded: () => void }) {
  const [models, setModels] = useState<AIModelRead[]>([])
  const [gatewayModels, setGatewayModels] = useState<GatewayModel[]>([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all')

  const load = useCallback(async () => {
    try {
      const current = await listAdminModels()
      setModels(current)
      setGatewayModels(current.map(({ name, provider, model_key }) => ({ name, provider, model_key })))
    } catch (e) {
      toast.error(getErrorMessage(e, 'خطا در دریافت مدل‌ها'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void Promise.resolve().then(load) }, [load])

  const activeKeys = new Set(models.filter(model => model.is_active).map(model => model.model_key))
  const filteredGatewayModels = gatewayModels.filter(model => {
    const current = models.find(item => item.model_key === model.model_key)
    const matchesSearch = [model.name, model.provider, model.model_key].some(value => value.toLowerCase().includes(search.trim().toLowerCase()))
    const matchesStatus = statusFilter === 'all' || (statusFilter === 'active' ? current?.is_active : !current?.is_active)
    return matchesSearch && matchesStatus
  })
  const toggle = (modelKey: string, is_active: boolean) => {
    setModels(current => {
      if (current.some(model => model.model_key === modelKey)) {
        return current.map(model => model.model_key === modelKey ? { ...model, is_active } : model)
      }
      const gateway = gatewayModels.find(model => model.model_key === modelKey)
      return gateway ? [...current, { id: 0, ...gateway, is_active, created_at: null }] : current
    })
  }

  const sync = async () => {
    setSyncing(true)
    try {
      setGatewayModels(await syncGatewayModels())
      toast.success('فهرست مدل‌های موجود دریافت شد؛ برای اعمال تغییرات ذخیره کنید')
    } catch (e) {
      toast.error(getErrorMessage(e, 'خطا در دریافت مدل‌ها'))
    } finally {
      setSyncing(false)
    }
  }

  const save = async () => {
    setSaving(true)
    try {
      const saved = await saveModelSelection(gatewayModels, [...activeKeys])
      setModels(saved)
      toast.success('وضعیت مدل‌ها ذخیره شد')
      onLoaded()
    } catch (e) {
      toast.error(getErrorMessage(e, 'خطا در ذخیره مدل‌ها'))
    } finally {
      setSaving(false)
    }
  }

  const disableAll = () => setModels(current => current.map(model => ({ ...model, is_active: false })))

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm font-medium text-muted-text">همگام‌سازی فقط مدل‌های موجود را نشان می‌دهد؛ تغییر وضعیت با ذخیره اعمال می‌شود.</p>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={disableAll} disabled={loading || saving}>غیرفعال‌کردن همه</Button>
          <Button variant="outline" disabled={syncing} onClick={() => void sync()}>{syncing ? 'در حال دریافت...' : 'نمایش مدل‌های Gateway'}</Button>
          <Button disabled={saving || loading} onClick={() => void save()} className="border-border bg-accent-neon text-primary-foreground shadow-[4px_4px_0_var(--color-shadow)] hover:bg-accent-neon/90 font-bold disabled:opacity-50">{saving ? 'در حال ذخیره...' : 'ذخیره وضعیت مدل‌ها'}</Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-3">
        <input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="جستجو در نام، ارائه‌دهنده یا کلید مدل..." className="min-w-64 flex-1 rounded-none border-2 border-border bg-card p-2.5 font-medium outline-none" />
        <select value={statusFilter} onChange={event => setStatusFilter(event.target.value as typeof statusFilter)} className="border-2 border-border bg-card px-3 font-bold">
          <option value="all">همه وضعیت‌ها</option>
          <option value="active">فعال</option>
          <option value="inactive">غیرفعال</option>
        </select>
      </div>

      <div className="border-2 border-border bg-card shadow-[6px_6px_0_var(--color-shadow)]">
        {loading ? (
          <div className="space-y-3 p-6">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-10 bg-accent" />)}</div>
        ) : !gatewayModels.length ? (
          <p className="p-6 text-sm font-medium text-muted-text">هنوز مدلی دریافت نشده؛ فهرست مدل‌های Gateway را دریافت کنید.</p>
        ) : (
          <Table>
            <TableHeader><TableRow><TableHead>نام</TableHead><TableHead>ارائه‌دهنده</TableHead><TableHead>کلید مدل</TableHead><TableHead>وضعیت</TableHead><TableHead className="text-center">فعال</TableHead></TableRow></TableHeader>
            <TableBody>
              {filteredGatewayModels.map(model => {
                const active = activeKeys.has(model.model_key)
                return <TableRow key={model.model_key}>
                  <TableCell className="font-bold">{model.name}</TableCell>
                  <TableCell>{model.provider}</TableCell>
                  <TableCell className="font-mono text-xs" dir="ltr">{model.model_key}</TableCell>
                  <TableCell><Badge variant={active ? 'default' : 'outline'} className="border-2 border-border font-bold">{active ? 'فعال' : 'غیرفعال'}</Badge></TableCell>
                  <TableCell className="text-center"><Switch checked={active} onCheckedChange={checked => toggle(model.model_key, checked)} aria-label={`تغییر وضعیت ${model.name}`} /></TableCell>
                </TableRow>
              })}
            </TableBody>
          </Table>
        )}
      </div>
    </section>
  )
}

function PromptsTab({ onLoaded }: { onLoaded: () => void }) {
  const [prompts, setPrompts] = useState<AdminPromptRead[]>([])
  const [loading, setLoading] = useState(true)
  const [includeArchived, setIncludeArchived] = useState(true)
  const [search, setSearch] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setPrompts(await listAdminPrompts({ include_archived: includeArchived, search }))
    } catch (e) {
      toast.error(getErrorMessage(e, 'خطا در دریافت پرامپت‌ها'))
    } finally {
      setLoading(false)
    }
  }, [includeArchived, search])

  useEffect(() => {
    const timer = setTimeout(() => { void load() }, search ? 300 : 0)
    return () => clearTimeout(timer)
  }, [load, search])

  const toggle = async (prompt: AdminPromptRead, is_active: boolean) => {
    try {
      const updated = await setAdminPromptActive(prompt.id, is_active)
      if (!includeArchived && !is_active) setPrompts(current => current.filter(p => p.id !== prompt.id))
      else setPrompts(current => current.map(p => (p.id === updated.id ? updated : p)))
      toast.success(is_active ? 'پرامپت بازگردانی شد' : 'پرامپت بایگانی شد')
      onLoaded()
    } catch (e) {
      toast.error(getErrorMessage(e, 'خطا در تغییر وضعیت پرامپت'))
    }
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <input type="search" value={search} onChange={e => setSearch(e.target.value)} placeholder="جستجو در متن پرامپت یا نام پروژه..." className="min-w-56 flex-1 rounded-none border-3 border-border bg-card p-2.5 font-medium outline-none font-vazirmatn" />
        <label className="flex cursor-pointer items-center gap-2 text-sm font-bold"><input type="checkbox" checked={includeArchived} onChange={e => setIncludeArchived(e.target.checked)} className="size-4 accent-accent-neon" />نمایش بایگانی‌شده‌ها</label>
      </div>

      {!loading && !prompts.length && <div className="border-2 border-border bg-card p-6 shadow-[6px_6px_0_var(--color-shadow)]"><p className="text-sm font-medium text-muted-text">پرامپتی یافت نشد.</p></div>}
      {loading && <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-20 bg-accent" />)}</div>}

      {!loading && !!prompts.length && <div className="space-y-3">
        {prompts.map(prompt => (
          <article key={prompt.id} className="border-2 border-border bg-card p-4 shadow-[6px_6px_0_var(--color-shadow)]">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <Badge variant="outline" className="border-2 border-border font-bold">{prompt.project_name || `پروژه #${prompt.project_id}`}</Badge>
                  <Badge variant={prompt.is_active ? 'default' : 'outline'} className="border-2 border-border font-bold">{prompt.is_active ? 'فعال' : 'بایگانی'}</Badge>
                  <span className="text-xs font-medium text-muted-text">آخرین اجرا: {prompt.last_run_at ? new Date(prompt.last_run_at).toLocaleString('fa-IR') : 'هنوز اجرا نشده'}</span>
                </div>
                <p className="whitespace-pre-wrap text-sm font-medium leading-relaxed">{prompt.text}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {prompt.models.map(model => <span key={model.id} className={`inline-flex items-center gap-1 border-2 px-2 py-0.5 text-xs font-bold ${model.is_active ? 'border-border' : 'border-destructive/60 text-muted-text'}`} title={model.model_key}>{model.name}{!model.is_active && <span className="border border-destructive/60 bg-destructive/10 px-1 py-px text-[10px] font-black text-destructive">منسوخ شده</span>}</span>)}
                  {!prompt.models.length && <span className="text-xs text-muted-text">بدون مدل</span>}
                </div>
              </div>
              <label className="flex shrink-0 cursor-pointer items-center gap-2 text-xs font-bold">{prompt.is_active ? 'فعال' : 'بایگانی'}<Switch checked={prompt.is_active} onCheckedChange={checked => void toggle(prompt, checked)} aria-label={`تغییر وضعیت پرامپت ${prompt.id}`} /></label>
            </div>
          </article>
        ))}
      </div>}
    </section>
  )
}

const EMPTY_SETTINGS: ExtractionSettings = { extraction_prompt: '', extraction_model: '', domain_format_instruction: '' }

function ExtractionTab() {
  const [settings, setSettings] = useState<ExtractionSettings>(EMPTY_SETTINGS)
  const [draft, setDraft] = useState<ExtractionSettings>(EMPTY_SETTINGS)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [models, setModels] = useState<AIModelRead[]>([])

  const apply = useCallback((value: ExtractionSettings) => { setSettings(value); setDraft(value) }, [])

  useEffect(() => {
    void Promise.all([getExtractionSettings(), listAdminModels()])
      .then(([value, availableModels]) => { apply(value); setModels(availableModels.filter(model => model.is_active)) })
      .catch(e => toast.error(getErrorMessage(e, 'خطا در دریافت تنظیمات')))
      .finally(() => setLoading(false))
  }, [apply])

  const dirty = JSON.stringify(settings) !== JSON.stringify(draft)

  const save = async () => {
    if ('{response_text}' in draft && !draft.extraction_prompt.includes('{response_text}')) {
      toast.error('پرامپت استخراج باید شامل {response_text} باشد')
      return
    }
    setSaving(true)
    try {
      apply(await updateExtractionSettings(draft))
      toast.success('تنظیمات ذخیره شد')
    } catch (e) {
      toast.error(getErrorMessage(e, 'خطا در ذخیره تنظیمات'))
    } finally {
      setSaving(false)
    }
  }

  const reset = async () => {
    try {
      apply(await resetExtractionSettings())
      toast.success('به حالت پیش‌فرض برگشت')
    } catch (e) {
      toast.error(getErrorMessage(e, 'خطا در بازنشانی تنظیمات'))
    }
  }

  if (loading) return <Skeleton className="h-96 bg-accent" />

  return (
    <section className="space-y-4">
      <div className="border-r-4 border-primary bg-card p-4">
        <h2 className="font-black">این تنظیمات برای چیست؟</h2>
        <ul className="mt-2 list-inside list-disc space-y-1 text-sm leading-6 text-muted-text">
          <li><b>دستور دامنه:</b> به همراه پرامپت کاربر به شرکت ارائه‌دهنده مدل فرستاده می‌شود.</li>
          <li><b>پرامپت استخراج:</b> پاسخ مدل اصلی را می‌گیرد، برندها را با رتبه تحلیل و برمی‌گرداند.</li>
          <li><b>مدل تحلیل‌گر:</b> مدلی که پاسخ را آنالیز و رتبه‌بندی می‌کند.</li>
        </ul>
      </div>

      <div className="space-y-5 border-2 border-border bg-card p-6 shadow-[6px_6px_0_var(--color-shadow)]">
        <label className="block space-y-2">
          <span className="text-sm font-black">مدل تحلیل‌گر (رتبه‌بندی پاسخ)</span>
          <select value={draft.extraction_model} onChange={e => setDraft(current => ({ ...current, extraction_model: e.target.value }))} dir="ltr" className="w-full rounded-none border-3 border-border bg-card p-2.5 font-mono text-sm outline-none">
            <option value="" disabled>مدل را انتخاب کنید</option>
            {models.map(model => <option key={model.id} value={model.model_key}>{model.model_key}</option>)}
          </select>
          <span className="block text-xs text-muted-text">مدل تحلیل‌گر را از مدل‌های فعال انتخاب کنید.</span>
        </label>

        <label className="block space-y-2">
          <span className="text-sm font-black">دستور دامنه (ضمیمه پرامپت کاربر)</span>
          <textarea value={draft.domain_format_instruction} onChange={e => setDraft(current => ({ ...current, domain_format_instruction: e.target.value }))} rows={3} dir="rtl" className="w-full resize-y rounded-none border-3 border-border p-3 text-sm font-medium leading-relaxed outline-none font-vazirmatn" />
          <span className="block text-xs text-muted-text">این متن بعد از پرامپت کاربر ارسال می‌شود تا مدل، نام برندها را با دامنه رسمی بنویسد.</span>
        </label>

        <label className="block space-y-2">
          <span className="text-sm font-black">پرامپت استخراج برند و رتبه</span>
          <textarea value={draft.extraction_prompt} onChange={e => setDraft(current => ({ ...current, extraction_prompt: e.target.value }))} rows={10} dir="ltr" className="w-full resize-y rounded-none border-3 border-border p-3 font-mono text-xs leading-relaxed outline-none" />
          <span className="block text-xs text-muted-text">باید شامل {'{response_text}'} باشد؛ خروجی باید JSON با ساختار brands باشد. تغییر نادرست باعث خطای استخراج می‌شود.</span>
        </label>

        <div className="flex flex-wrap gap-3 border-t-2 border-border pt-4">
          <Button disabled={!dirty || saving} onClick={save} className="border-border bg-accent-neon text-primary-foreground shadow-[4px_4px_0_var(--color-shadow)] hover:bg-accent-neon/90 font-bold disabled:opacity-50">{saving ? 'در حال ذخیره...' : 'ذخیره'}</Button>
          <Button variant="outline" disabled={!dirty} onClick={() => setDraft(settings)} className="border-border font-bold">انصراف</Button>
          <Button variant="outline" onClick={reset} className="mr-auto border-border font-bold">بازگشت به پیش‌فرض</Button>
        </div>
      </div>
    </section>
  )
}

function BrandsTab() {
  const [brands, setBrands] = useState<AdminBrand[]>([])
  const [canonicalId, setCanonicalId] = useState('')
  const [sourceIds, setSourceIds] = useState<number[]>([])
  const [preview, setPreview] = useState<BrandMergePreview | null>(null)
  const [previewKey, setPreviewKey] = useState('')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [previewing, setPreviewing] = useState(false)
  const [merging, setMerging] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)

  const load = useCallback(async () => {
    try {
      const result = await listAdminBrands()
      setBrands(result)
      setCanonicalId(current => result.some(brand => String(brand.id) === current) ? current : '')
    } catch (e) {
      toast.error(getErrorMessage(e, 'خطا در دریافت برندها'))
    } finally {
      setLoading(false)
    }
  }, [])
  useEffect(() => { void Promise.resolve().then(load) }, [load])

  const currentKey = JSON.stringify([Number(canonicalId), [...sourceIds].sort((a, b) => a - b)])
  const filtered = brands.filter(brand => `${brand.name} ${brand.domain}`.toLowerCase().includes(search.trim().toLowerCase()))
  const selectedCanonical = brands.find(brand => String(brand.id) === canonicalId)
  const previewIsCurrent = Boolean(preview && previewKey === currentKey)

  const updateSources = (next: number[]) => {
    setSourceIds(next)
    setPreview(null)
  }

  const previewMerge = async () => {
    if (!canonicalId || sourceIds.length === 0) return
    setPreviewing(true)
    setPreview(null)
    try {
      const result = await previewAdminBrandMerge({ canonical_id: Number(canonicalId), source_ids: sourceIds })
      setPreview(result)
      setPreviewKey(currentKey)
    } catch (e) {
      toast.error(getErrorMessage(e, 'پیش‌نمایش ادغام ناموفق بود'))
    } finally {
      setPreviewing(false)
    }
  }

  const merge = async () => {
    if (!previewIsCurrent) return
    setMerging(true)
    try {
      const result = await mergeAdminBrands({ canonical_id: Number(canonicalId), source_ids: sourceIds })
      toast.success(`${result.merged_ids.length.toLocaleString('fa-IR')} برند در «${result.canonical.name}» ادغام شد`)
      setConfirmOpen(false)
      setSourceIds([])
      setPreview(null)
      setPreviewKey('')
      await load()
    } catch (e) {
      toast.error(getErrorMessage(e, 'ادغام برندها انجام نشد'))
    } finally {
      setMerging(false)
    }
  }

  return (
    <section className="space-y-4">
      <div className="border border-border bg-card p-4 text-sm leading-6 text-muted-text">
        چند نام متفاوت را به یک برند اصلی وصل کنید. نام‌های قبلی و دامنه‌ها حفظ می‌شوند و در استخراج‌های بعدی هم به برند اصلی متصل خواهند شد.
      </div>
      <div className="grid gap-3 border-2 border-border bg-card p-4 md:grid-cols-[minmax(0,1fr)_minmax(16rem,24rem)] md:items-end">
        <label className="grid gap-2 text-sm font-bold">
          جستجوی برند
          <Input value={search} onChange={event => setSearch(event.target.value)} placeholder="نام یا دامنه..." />
        </label>
        <label className="grid gap-2 text-sm font-bold">
          برند اصلی که حفظ می‌شود
          <Select value={canonicalId} disabled={previewing || merging} onValueChange={value => { setCanonicalId(value); updateSources(sourceIds.filter(id => String(id) !== value)) }}>
            <SelectTrigger className="border-border bg-background"><SelectValue placeholder="انتخاب برند اصلی" /></SelectTrigger>
            <SelectContent>
              {brands.map(brand => <SelectItem key={brand.id} value={String(brand.id)}>{brand.name} — {brand.domain}</SelectItem>)}
            </SelectContent>
          </Select>
        </label>
      </div>
      <div className="overflow-x-auto border-2 border-border bg-card">
        <Table>
          <TableHeader><TableRow><TableHead>انتخاب برای ادغام</TableHead><TableHead>برند</TableHead><TableHead>دامنه</TableHead><TableHead>رکورد رتبه</TableHead><TableHead>پروژه</TableHead><TableHead>نام مستعار</TableHead></TableRow></TableHeader>
          <TableBody>
            {loading ? <TableRow><TableCell colSpan={6} className="py-8 text-center">در حال دریافت برندها...</TableCell></TableRow> : filtered.length === 0 ? <TableRow><TableCell colSpan={6} className="py-8 text-center text-muted-text">برندی پیدا نشد.</TableCell></TableRow> : filtered.map(brand => {
              const checked = sourceIds.includes(brand.id)
              const isCanonical = String(brand.id) === canonicalId
              return <TableRow key={brand.id}>
                <TableCell><input type="checkbox" aria-label={`ادغام ${brand.name}`} checked={checked} disabled={isCanonical || previewing || merging} onChange={event => updateSources(event.target.checked ? [...sourceIds, brand.id] : sourceIds.filter(id => id !== brand.id))} className="size-4 accent-primary disabled:opacity-40" /></TableCell>
                <TableCell className="font-bold">{brand.name}{isCanonical && <Badge className="ms-2">اصلی</Badge>}</TableCell>
                <TableCell dir="ltr" className="text-start text-xs">{brand.domain}</TableCell>
                <TableCell>{brand.run_links.toLocaleString('fa-IR')}</TableCell>
                <TableCell>{brand.project_links.toLocaleString('fa-IR')}</TableCell>
                <TableCell>{brand.aliases.toLocaleString('fa-IR')}</TableCell>
              </TableRow>
            })}
          </TableBody>
        </Table>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <Button type="button" variant="outline" disabled={!canonicalId || sourceIds.length === 0 || previewing || merging} onClick={previewMerge}>
          {previewing ? 'در حال پیش‌نمایش...' : 'پیش‌نمایش ادغام'}
        </Button>
        {previewIsCurrent && preview && preview.conflicts.length === 0 && <Button type="button" disabled={merging} onClick={() => setConfirmOpen(true)}>تأیید و ادغام</Button>}
      </div>
      {previewIsCurrent && preview && (
        <div className="space-y-2 border-2 border-border bg-card p-4 text-sm">
          {preview.conflicts.length > 0 && <div role="alert" className="border border-red-500/40 bg-red-500/10 p-3 font-bold text-red-300">این ادغام به‌دلیل تداخل هویت قابل انجام نیست:
            <ul className="mt-2 list-disc pe-5 font-medium">{preview.conflicts.map(conflict => <li key={conflict}>{conflict}</li>)}</ul>
          </div>}
          <p className="font-black">برند اصلی: {preview.canonical.name} ({preview.canonical.domain})</p>
          <p>برندهای ادغام‌شونده: {preview.sources.map(brand => `${brand.name} (${brand.domain})`).join('، ')}</p>
          <p className="text-muted-text">پیوندهای رتبه: {preview.run_links_to_move.toLocaleString('fa-IR')}؛ پیوندهای پروژه: {preview.project_links_to_repoint.toLocaleString('fa-IR')}؛ نام/دامنه‌های حفظ‌شونده: {preview.aliases_to_preserve.toLocaleString('fa-IR')}؛ رکوردهای تکراری همان اجرا که حذف می‌شوند: {preview.duplicate_run_links_to_remove.toLocaleString('fa-IR')} (رتبه بهتر حفظ می‌شود).</p>
        </div>
      )}
      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent dir="rtl">
          <AlertDialogHeader>
            <AlertDialogTitle>ادغام برندها تأیید شود؟</AlertDialogTitle>
            <AlertDialogDescription>
              {selectedCanonical ? `همه نام‌ها و رکوردهای انتخاب‌شده به «${selectedCanonical.name}» منتقل می‌شوند. این عملیات پس از تأیید قابل بازگشت نیست.` : 'این عملیات پس از تأیید قابل بازگشت نیست.'}
              {preview && ` ${preview.duplicate_run_links_to_remove.toLocaleString('fa-IR')} رکورد تکراری رتبه حذف خواهد شد.`}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={merging}>انصراف</AlertDialogCancel>
            <Button type="button" variant="destructive" disabled={merging} onClick={() => void merge()}>{merging ? 'در حال ادغام...' : 'ادغام قطعی'}</Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  )
}

function CostsTab() {
  const [items, setItems] = useState<AdminCostItem[]>([])
  useEffect(() => { void getAdminCosts().then(setItems).catch(e => toast.error(getErrorMessage(e, 'خطا در دریافت هزینه‌ها'))) }, [])
  const total = items.reduce((sum, item) => sum + (item.cost_irt || 0), 0)
  return <section className="space-y-4">
    <div className="border-2 border-border bg-card p-4 font-bold">مجموع هزینه: {total.toLocaleString('fa-IR')} تومان</div>
    <div className="overflow-x-auto border-2 border-border bg-card">
      <Table><TableHeader><TableRow><TableHead>زمان</TableHead><TableHead>مدل</TableHead><TableHead>ارائه‌دهنده مدل</TableHead><TableHead>مسیر اجرا</TableHead><TableHead>توکن ورودی</TableHead><TableHead>توکن خروجی</TableHead><TableHead>مجموع توکن</TableHead><TableHead>هزینه</TableHead><TableHead>وضعیت</TableHead></TableRow></TableHeader><TableBody>
        {items.map(item => <TableRow key={item.id}><TableCell className="text-xs">{new Date(item.created_at).toLocaleString('fa-IR')}</TableCell><TableCell dir="ltr">{item.model}</TableCell><TableCell>{item.model_provider || '-'}</TableCell><TableCell>{item.execution_provider || '-'}</TableCell><TableCell>{(item.prompt_tokens || 0).toLocaleString('fa-IR')}</TableCell><TableCell>{(item.completion_tokens || 0).toLocaleString('fa-IR')}</TableCell><TableCell>{(item.total_tokens || 0).toLocaleString('fa-IR')}</TableCell><TableCell>{item.cost_irt == null ? '-' : `${item.cost_irt.toLocaleString('fa-IR')} تومان`}</TableCell><TableCell>{item.status}</TableCell></TableRow>)}
      </TableBody></Table>
    </div>
  </section>
}

function ReferencesTab() {
  const [refs, setRefs] = useState<AdminReference[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const pageSize = 50

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await listAdminReferences({ search: query, page, page_size: pageSize })
      setRefs(result.items)
      setTotal(result.total)
    } catch (e) {
      toast.error(getErrorMessage(e, 'خطا در دریافت رفرنس‌ها'))
    } finally {
      setLoading(false)
    }
  }, [query, page])

  useEffect(() => { void load() }, [load])

  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <p className="text-sm font-medium text-muted-text">رفرنس‌هایی که مدل‌ها هنگام جستجوی وب به آن‌ها استناد کرده‌اند.</p>
        <form
          className="flex gap-2"
          onSubmit={e => { e.preventDefault(); setPage(1); setQuery(search.trim()) }}
        >
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="جستجو در آدرس رفرنس..."
            dir="ltr"
            className="w-64 rounded-none border-2 border-border bg-card p-2 text-sm outline-none"
            aria-label="جستجو در آدرس رفرنس"
          />
          <Button type="submit" className="border-border bg-accent-neon text-primary-foreground shadow-[4px_4px_0_var(--color-shadow)] hover:bg-accent-neon/90 font-bold">جستجو</Button>
        </form>
      </div>

      <div className="border-2 border-border bg-card shadow-[6px_6px_0_var(--color-shadow)]">
        {loading ? (
          <div className="space-y-3 p-6">{Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-10 bg-accent" />)}</div>
        ) : !refs.length ? (
          <p className="p-6 text-sm font-medium text-muted-text">هنوز رفرنسی ثبت نشده است.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>رفرنس</TableHead>
                <TableHead>پروژه</TableHead>
                <TableHead>پرامپت</TableHead>
                <TableHead>مدل</TableHead>
                <TableHead>تاریخ</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {refs.map(ref => (
                <TableRow key={`${ref.prompt_id}-${ref.ai_model_id}-${ref.url}`}>
                  <TableCell className="max-w-72 truncate font-mono text-xs" dir="ltr">
                    <a href={ref.url} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 hover:text-primary" title={ref.url}>{ref.url}</a>
                  </TableCell>
                  <TableCell className="font-bold">{ref.project_name}</TableCell>
                  <TableCell className="max-w-72 truncate text-sm text-muted-text" title={ref.prompt}>{ref.prompt}</TableCell>
                  <TableCell>{ref.ai_model}</TableCell>
                  <TableCell className="text-xs">{new Date(ref.run_date).toLocaleDateString('fa-IR')}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      <div className="flex items-center justify-between text-sm font-bold">
        <span>مجموع: {total.toLocaleString('fa-IR')}</span>
        <div className="flex items-center gap-2">
          <Button variant="outline" disabled={page <= 1} onClick={() => setPage(p => p - 1)} className="border-border">قبلی</Button>
          <span>صفحه {page.toLocaleString('fa-IR')} از {totalPages.toLocaleString('fa-IR')}</span>
          <Button variant="outline" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)} className="border-border">بعدی</Button>
        </div>
      </div>
    </section>
  )
}
