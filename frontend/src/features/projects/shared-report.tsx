import { useEffect, useState, type ReactNode } from 'react'
import { useParams } from '@tanstack/react-router'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { getSharedReport, type SharedReport } from '@/lib/api'

export function SharedReportPage() {
  const { token } = useParams({ from: '/shared/$token' })
  const [report, setReport] = useState<SharedReport | null>(null)
  const [hasError, setHasError] = useState(false)

  useEffect(() => {
    let cancelled = false
    getSharedReport(token)
      .then((data) => { if (!cancelled) setReport(data) })
      .catch(() => { if (!cancelled) setHasError(true) })
    return () => { cancelled = true }
  }, [token])

  if (hasError) return <PageShell><Card className="border-border"><CardContent className="py-12 text-center"><h1 className="text-xl font-black">این لینک معتبر نیست</h1><p className="mt-2 text-sm text-muted-text">ممکن است لینک منقضی یا لغو شده باشد.</p></CardContent></Card></PageShell>
  if (!report) return <PageShell><Skeleton className="h-48 w-full bg-accent" /></PageShell>

  const successfulRuns = report.runs.filter((run) => run.status === 'success').length
  return <PageShell><Card className="border-border shadow-[6px_6px_0_var(--color-shadow)]"><CardHeader><h1 className="text-xl font-black">گزارش اشتراکی</h1><p className="text-sm text-muted-text">آخرین اجراهای پروژه</p></CardHeader><CardContent className="space-y-6"><dl className="grid grid-cols-2 gap-3 sm:grid-cols-3"><Metric label="کل اجراها" value={report.runs.length} /><Metric label="موفق" value={successfulRuns} /><Metric label="ناموفق" value={report.runs.length - successfulRuns} /></dl>{report.runs.length ? <div className="overflow-x-auto border border-border"><table className="w-full min-w-140 text-right text-sm"><thead className="bg-accent text-muted-text"><tr><th className="p-3 font-bold">مدل</th><th className="p-3 font-bold">وضعیت</th><th className="p-3 font-bold">زمان اجرا</th></tr></thead><tbody>{report.runs.map((run, index) => <tr key={`${run.model}-${run.created_at}-${index}`} className="border-t border-border"><td className="p-3" dir="ltr">{run.model}</td><td className="p-3"><Badge variant={run.status === 'success' ? 'default' : 'destructive'}>{run.status === 'success' ? 'موفق' : 'ناموفق'}</Badge></td><td className="p-3 whitespace-nowrap">{new Date(run.created_at).toLocaleString('fa-IR')}</td></tr>)}</tbody></table></div> : <p className="text-sm text-muted-text">اجرایی برای نمایش وجود ندارد.</p>}</CardContent></Card></PageShell>
}

function Metric({ label, value }: { label: string; value: number }) {
  return <div className="border border-border bg-accent p-3"><dt className="text-xs text-muted-text">{label}</dt><dd className="mt-1 text-2xl font-black">{value}</dd></div>
}

function PageShell({ children }: { children: ReactNode }) {
  return <main className="min-h-screen bg-bg p-4 font-vazirmatn sm:p-8" dir="rtl"><div className="mx-auto w-full max-w-4xl">{children}</div></main>
}
