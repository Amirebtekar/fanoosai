import { useEffect, useMemo, useRef, useState } from 'react'
import {
  type ColumnDef,
  type FilterFn,
  type PaginationState,
  type SortingState,
  type VisibilityState,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from '@tanstack/react-table'
import { addDays, format, parseISO } from 'date-fns'
import { ArrowDown, ArrowUp, Download, Maximize2, Minimize2, Printer } from 'lucide-react'
import { toast } from 'sonner'
import {
  getErrorMessage,
  getRankReport,
  listObservedBrands,
  listProjectBrands,
  type RankReport,
  type RankReportRow,
} from '@/lib/api'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { DataTableColumnHeader } from '@/components/data-table/column-header'
import { DataTablePagination } from '@/components/data-table/pagination'
import { DataTableToolbar } from '@/components/data-table/toolbar'
import { DatePicker } from '@/components/date-picker'

type BrandOption = { value: string; label: string }

const rankReportFilter: FilterFn<RankReportRow> = (row, _columnId, value) => {
  const query = String(value ?? '').trim().toLowerCase()
  if (!query) return true
  return (
    row.original.prompt.toLowerCase().includes(query) ||
    row.original.ai_model.toLowerCase().includes(query)
  )
}

function RankCell({ value }: { value: number | null | undefined }) {
  if (value == null) return <span className='text-muted-text'>—</span>
  return <span className='font-bold tabular-nums'>{value}</span>
}

function ChangeCell({ value }: { value: number | null }) {
  if (value == null) return <span className='text-muted-text'>—</span>
  if (value === 0) return <span className='text-muted-text'>0</span>
  const improved = value < 0
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 font-bold tabular-nums',
        improved ? 'print-accent-good text-emerald-400' : 'print-accent-bad text-red-400'
      )}
    >
      {improved ? <ArrowDown className='size-3.5' aria-hidden='true' /> : <ArrowUp className='size-3.5' aria-hidden='true' />}
      {value > 0 ? `+${value}` : value}
    </span>
  )
}

type RankReportProps = { projectId: number }

export function RankReport({ projectId }: RankReportProps) {
  const [brands, setBrands] = useState<BrandOption[]>([])
  const [brandId, setBrandId] = useState('')
  const [startDate, setStartDate] = useState<Date | undefined>(() => addDays(new Date(), -6))
  const [endDate, setEndDate] = useState<Date | undefined>(() => new Date())
  const [report, setReport] = useState<RankReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const [sorting, setSorting] = useState<SortingState>([{ id: 'prompt', desc: false }])
  const [globalFilter, setGlobalFilter] = useState('')
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({})
  const [pagination, setPagination] = useState<PaginationState>({ pageIndex: 0, pageSize: 10 })

  const containerRef = useRef<HTMLDivElement>(null)
  const [fullscreen, setFullscreen] = useState(false)

  const dateError =
    startDate && endDate && startDate > endDate ? 'تاریخ شروع باید قبل از تاریخ پایان باشد.' : ''

  useEffect(() => {
    if (!projectId) {
      setBrands([])
      setBrandId('')
      setReport(null)
      return
    }
    let cancelled = false
    Promise.all([listObservedBrands(projectId), listProjectBrands(projectId)])
      .then(([observed, configured]) => {
        if (cancelled) return
        const labels = new Map<number, string>()
        configured.forEach((brand) => {
          if (brand.brand_id && !labels.has(brand.brand_id)) labels.set(brand.brand_id, brand.name)
        })
        observed.forEach((brand) => {
          if (!labels.has(brand.brand_id)) labels.set(brand.brand_id, brand.name)
        })
        const ownedIds = new Set(
          configured.filter((brand) => brand.kind === 'owned' && brand.brand_id).map((brand) => brand.brand_id as number)
        )
        const options = [...labels.entries()]
          .map(([value, label]) => ({ value: String(value), label }))
          .sort((a, b) => {
            const owned = Number(ownedIds.has(Number(b.value))) - Number(ownedIds.has(Number(a.value)))
            return owned || a.label.localeCompare(b.label, 'fa')
          })
        setBrands(options)
        setBrandId((previous) => (options.some((option) => option.value === previous) ? previous : (options[0]?.value ?? '')))
      })
      .catch(() => {
        if (!cancelled) toast.error('دریافت برندها ممکن نشد')
      })
    return () => {
      cancelled = true
    }
  }, [projectId])

  useEffect(() => {
    if (!projectId || !brandId || !startDate || !endDate || startDate > endDate) {
      setReport(null)
      return
    }
    let cancelled = false
    setLoading(true)
    getRankReport(projectId, {
      brand_id: Number(brandId),
      start_date: format(startDate, 'yyyy-MM-dd'),
      end_date: format(endDate, 'yyyy-MM-dd'),
    })
      .then((result) => {
        if (cancelled) return
        setReport(result)
        setError('')
      })
      .catch((e) => {
        if (cancelled) return
        setReport(null)
        setError(getErrorMessage(e, 'دریافت گزارش ممکن نشد'))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [projectId, brandId, startDate, endDate])

  useEffect(() => setPagination((previous) => ({ ...previous, pageIndex: 0 })), [report])

  useEffect(() => {
    const onChange = () => setFullscreen(Boolean(document.fullscreenElement))
    document.addEventListener('fullscreenchange', onChange)
    return () => document.removeEventListener('fullscreenchange', onChange)
  }, [])

  const todayKey = format(new Date(), 'yyyy-MM-dd')
  const yesterdayKey = format(addDays(new Date(), -1), 'yyyy-MM-dd')
  const otherDays = useMemo(
    () => (report?.days ?? []).filter((day) => day !== todayKey && day !== yesterdayKey).reverse(),
    [report?.days, todayKey, yesterdayKey]
  )

  const columns = useMemo<ColumnDef<RankReportRow>[]>(() => {
    const dayColumn = (day: string): ColumnDef<RankReportRow> => ({
      id: day,
      meta: { label: format(parseISO(day), 'yyyy/MM/dd') },
      accessorFn: (row) => row.daily[day] ?? 999,
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title={format(parseISO(day), 'yyyy/MM/dd')} className='justify-start' />
      ),
      cell: ({ row }) => <RankCell value={row.original.daily[day]} />,
    })

    return [
      {
        id: 'prompt',
        meta: { label: 'کلمه کلیدی' },
        accessorFn: (row) => row.prompt,
        header: ({ column }) => <DataTableColumnHeader column={column} title='کلمه کلیدی' />,
        cell: ({ row }) => (
          <span className='line-clamp-2 max-w-72 whitespace-normal' title={row.original.prompt}>
            {row.original.prompt}
          </span>
        ),
      },
      {
        id: 'model',
        meta: { label: 'مدل' },
        accessorFn: (row) => row.ai_model,
        header: ({ column }) => <DataTableColumnHeader column={column} title='مدل' />,
        cell: ({ row }) => <span className='font-medium'>{row.original.ai_model}</span>,
      },
      {
        id: 'average',
        meta: { label: 'میانگین رتبه' },
        accessorFn: (row) => row.average_rank ?? 999,
        header: ({ column }) => <DataTableColumnHeader column={column} title='میانگین رتبه' />,
        cell: ({ row }) => <RankCell value={row.original.average_rank} />,
      },
      {
        id: 'change',
        meta: { label: 'تغییر' },
        accessorFn: (row) => row.rank_change ?? 0,
        header: ({ column }) => <DataTableColumnHeader column={column} title='تغییر' />,
        cell: ({ row }) => <ChangeCell value={row.original.rank_change} />,
      },
      {
        id: 'today',
        meta: { label: 'امروز' },
        accessorFn: (row) => row.daily[todayKey] ?? 999,
        header: ({ column }) => <DataTableColumnHeader column={column} title='امروز' />,
        cell: ({ row }) => <RankCell value={row.original.daily[todayKey]} />,
      },
      {
        id: 'yesterday',
        meta: { label: 'دیروز' },
        accessorFn: (row) => row.daily[yesterdayKey] ?? 999,
        header: ({ column }) => <DataTableColumnHeader column={column} title='دیروز' />,
        cell: ({ row }) => <RankCell value={row.original.daily[yesterdayKey]} />,
      },
      ...otherDays.map(dayColumn),
    ]
  }, [otherDays, todayKey, yesterdayKey])

  const table = useReactTable({
    data: report?.items ?? [],
    columns,
    state: { sorting, globalFilter, columnVisibility, pagination },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    onColumnVisibilityChange: setColumnVisibility,
    onPaginationChange: setPagination,
    globalFilterFn: rankReportFilter,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  })

  const exportCsv = () => {
    const header = [
      'کلمه کلیدی',
      'مدل',
      'میانگین رتبه',
      'تغییر',
      'امروز',
      'دیروز',
      ...otherDays.map((day) => format(parseISO(day), 'yyyy/MM/dd')),
    ]
    const body = table.getFilteredRowModel().rows.map(({ original }) => [
      original.prompt,
      original.ai_model,
      original.average_rank ?? '',
      original.rank_change ?? '',
      original.daily[todayKey] ?? '',
      original.daily[yesterdayKey] ?? '',
      ...otherDays.map((day) => original.daily[day] ?? ''),
    ])
    const escape = (value: string | number) => `"${String(value).replace(/"/g, '""')}"`
    const csv = `\uFEFF${[header, ...body].map((line) => line.map(escape).join(',')).join('\r\n')}`
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
    const link = document.createElement('a')
    link.href = url
    link.download = `rank-report-${format(new Date(), 'yyyyMMdd-HHmm')}.csv`
    link.click()
    URL.revokeObjectURL(url)
  }

  const toggleFullscreen = () => {
    if (document.fullscreenElement) void document.exitFullscreen()
    else void containerRef.current?.requestFullscreen?.()
  }

  return (
    <section aria-label='گزارش روزانه رتبه‌ها'>
      <div className='mb-4'>
        <h2 className='text-xl font-black'>گزارش روزانه رتبه‌ها</h2>
        <p className='text-sm font-medium text-muted-text'>
          میانگین رتبه برند انتخاب‌شده برای هر پرامپت و مدل در بازه زمانی انتخابی.
        </p>
      </div>

      <div className='mb-4 flex flex-col gap-3 sm:flex-row sm:items-end'>
        <div className='grid gap-2 sm:w-64'>
          <label htmlFor='rank-report-brand' className='text-sm font-semibold'>
            برند
          </label>
          <Select value={brandId} onValueChange={setBrandId} disabled={!projectId || brands.length === 0}>
            <SelectTrigger id='rank-report-brand' className='w-full border-border font-medium'>
              <SelectValue
                placeholder={
                  !projectId
                    ? 'ابتدا پروژه را انتخاب کنید'
                    : brands.length
                      ? 'انتخاب برند...'
                      : 'برندی یافت نشد'
                }
              />
            </SelectTrigger>
            <SelectContent>
              {brands.map((brand) => (
                <SelectItem key={brand.value} value={brand.value}>
                  {brand.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className='grid gap-2 sm:w-52'>
          <span className='text-sm font-semibold'>از تاریخ</span>
          <DatePicker selected={startDate} onSelect={setStartDate} placeholder='تاریخ شروع' />
        </div>
        <div className='grid gap-2 sm:w-52'>
          <span className='text-sm font-semibold'>تا تاریخ</span>
          <DatePicker selected={endDate} onSelect={setEndDate} placeholder='تاریخ پایان' />
        </div>
      </div>

      {dateError && (
        <p role='alert' className='mb-4 text-sm font-medium text-destructive'>
          {dateError}
        </p>
      )}

      <div
        ref={containerRef}
        className='border-3 border-border bg-card shadow-[6px_6px_0_var(--color-shadow)] print:shadow-none'
      >
        <div className='no-print flex flex-wrap items-center gap-2 border-b border-border p-3'>
          <div className='min-w-0 flex-1'>
            <DataTableToolbar table={table} searchPlaceholder='جستجو ...' />
          </div>
          <div className='flex items-center gap-1'>
            <Button
              type='button'
              variant='outline'
              size='sm'
              className='size-8 p-0'
              onClick={exportCsv}
              disabled={!report?.items.length}
              aria-label='دانلود CSV'
              title='دانلود CSV'
            >
              <Download className='size-4' aria-hidden='true' />
            </Button>
            <Button
              type='button'
              variant='outline'
              size='sm'
              className='size-8 p-0'
              onClick={() => window.print()}
              aria-label='چاپ گزارش'
              title='چاپ گزارش'
            >
              <Printer className='size-4' aria-hidden='true' />
            </Button>
            <Button
              type='button'
              variant='outline'
              size='sm'
              className='size-8 p-0'
              onClick={toggleFullscreen}
              aria-label='تمام صفحه'
              title='تمام صفحه'
            >
              {fullscreen ? <Minimize2 className='size-4' aria-hidden='true' /> : <Maximize2 className='size-4' aria-hidden='true' />}
            </Button>
          </div>
        </div>

        {error && (
          <div role='alert' className='border-b border-border bg-red-50 p-3 text-sm font-bold text-red-700'>
            {error}
          </div>
        )}

        {loading && (
          <div className='space-y-3 p-4'>
            {Array.from({ length: 5 }).map((_, index) => (
              <Skeleton key={index} className='h-8 w-full bg-accent' />
            ))}
          </div>
        )}

        {!loading && !error && table.getRowModel().rows.length === 0 && (
          <div className='flex flex-col items-center gap-3 p-10 text-center'>
            <h3 className='text-lg font-black'>داده‌ای وجود ندارد</h3>
            <p className='text-sm font-medium text-muted-text'>
              {!projectId
                ? 'برای نمایش گزارش ابتدا یک پروژه انتخاب کنید.'
                : brandId
                  ? 'برای این برند و بازه زمانی رتبه‌ای ثبت نشده است.'
                  : 'ابتدا یک برند برای نمایش گزارش انتخاب کنید.'}
            </p>
          </div>
        )}

        {!loading && table.getRowModel().rows.length > 0 && (
          <Table>
            <TableHeader>
              {table.getHeaderGroups().map((headerGroup) => (
                <TableRow key={headerGroup.id} className='hover:bg-transparent'>
                  {headerGroup.headers.map((header) => (
                    <TableHead key={header.id} className='bg-muted/40 font-black'>
                      {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                    </TableHead>
                  ))}
                </TableRow>
              ))}
            </TableHeader>
            <TableBody>
              {table.getRowModel().rows.map((row) => (
                <TableRow key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}

        {table.getRowModel().rows.length > 0 && (
          <div className='border-t border-border p-2'>
            <DataTablePagination table={table} />
          </div>
        )}
      </div>
    </section>
  )
}
