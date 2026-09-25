import { useMemo, useState } from 'react'
import { Check, Plus, Search, X } from 'lucide-react'
import type { AIModelRead } from '@/lib/api'
import { cn } from '@/lib/utils'
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { filterModels, groupModelsByProvider } from './model-picker-utils'

type ModelMultiSelectProps = {
  models: AIModelRead[]
  selectedIds: number[]
  onToggle: (id: number) => void
  onClear?: () => void
}

export function ModelMultiSelect({ models, selectedIds, onToggle, onClear }: ModelMultiSelectProps) {
  const [query, setQuery] = useState('')
  const filtered = useMemo(() => filterModels(models, query), [models, query])
  const groups = useMemo(() => groupModelsByProvider(filtered), [filtered])
  const selected = useMemo(() => new Set(selectedIds), [selectedIds])
  const selectedModels = useMemo(
    () => selectedIds.map(id => models.find(model => model.id === id)).filter((model): model is AIModelRead => Boolean(model)),
    [models, selectedIds],
  )

  const selectVisible = () => {
    for (const model of filtered) if (!selected.has(model.id)) onToggle(model.id)
  }
  const deselectVisible = () => {
    for (const model of filtered) if (selected.has(model.id)) onToggle(model.id)
  }

  return (
    <div className="space-y-3" dir="rtl">
      <div className="relative">
        <Search className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
        <input
          type="search"
          value={query}
          onChange={event => setQuery(event.target.value)}
          placeholder="جستجو: gpt، claude، google…"
          aria-label="جستجوی مدل"
          className="w-full rounded-none border-3 border-border bg-card py-2.5 pr-9 pl-3 text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring font-vazirmatn"
        />
      </div>

      {!!selectedModels.length && (
        <div className="flex flex-wrap gap-1.5" aria-label="مدل‌های انتخاب‌شده">
          {selectedModels.map(model => (
            <button
              key={model.id}
              type="button"
              onClick={() => onToggle(model.id)}
              className="inline-flex items-center gap-1 border-2 border-border bg-accent-neon/20 px-2 py-0.5 text-xs font-bold hover:border-destructive/60"
              aria-label={`حذف ${model.name}`}
            >
              {model.name}
              <X className="size-3" aria-hidden="true" />
            </button>
          ))}
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-2 text-xs font-medium text-muted-text">
        <span>
          {selectedIds.length} انتخاب شده · {filtered.length} از {models.length} نتیجه
        </span>
        <span className="flex gap-3">
          <button type="button" className="font-bold text-foreground underline-offset-2 hover:underline" onClick={selectVisible}>
            انتخاب همه نتایج
          </button>
          <button type="button" className="font-bold text-foreground underline-offset-2 hover:underline" onClick={deselectVisible}>
            حذف نتایج
          </button>
          {onClear && selectedIds.length > 0 && (
            <button type="button" className="font-bold text-destructive underline-offset-2 hover:underline" onClick={onClear}>
              پاک کردن همه
            </button>
          )}
        </span>
      </div>

      <div className="max-h-60 overflow-y-auto border-2 border-border bg-card" role="listbox" aria-label="فهرست مدل‌ها" aria-multiselectable="true">
        {groups.map(group => (
          <div key={group.provider} role="group" aria-label={group.provider}>
            <div className="sticky top-0 z-10 border-b border-border bg-muted px-3 py-1.5 text-[11px] font-black text-muted-text">
              {group.provider}
              <span className="font-medium"> · {group.models.length}</span>
            </div>
            {group.models.map(model => {
              const isSelected = selected.has(model.id)
              return (
                <button
                  key={model.id}
                  type="button"
                  role="option"
                  aria-selected={isSelected}
                  onClick={() => onToggle(model.id)}
                  className={cn(
                    'flex w-full items-center gap-2 border-b border-border/50 px-3 py-2 text-right text-sm transition-colors',
                    isSelected ? 'bg-accent-neon/15 font-bold' : 'hover:bg-accent/60',
                  )}
                >
                  <span className={cn('flex size-4 shrink-0 items-center justify-center border-2 border-border', isSelected && 'bg-accent-neon text-primary-foreground')}>
                    {isSelected && <Check className="size-3" aria-hidden="true" />}
                  </span>
                  <span className="flex-1 truncate font-medium" dir="ltr">{model.name}</span>
                  {!model.is_active && (
                    <span className="border border-destructive/60 bg-destructive/10 px-1 py-px text-[10px] font-black text-destructive">منسوخ</span>
                  )}
                </button>
              )
            })}
          </div>
        ))}
        {!groups.length && (
          <p className="p-4 text-center text-sm text-muted-text">
            مدلی با «{query.trim()}» پیدا نشد؛ عبارت دیگری امتحان کنید.
          </p>
        )}
      </div>
    </div>
  )
}

type AddModelMenuProps = {
  models: AIModelRead[]
  onAdd: (modelId: number) => void
  className?: string
}

export function AddModelMenu({ models, onAdd, className }: AddModelMenuProps) {
  const [open, setOpen] = useState(false)
  const groups = useMemo(() => groupModelsByProvider(models), [models])

  if (!models.length) return null

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          onClick={event => event.stopPropagation()}
          className={cn('prompt-action inline-flex items-center gap-1 border-2 border-border bg-card px-2 py-0.5 text-xs font-bold', className)}
          aria-haspopup="menu"
          aria-expanded={open}
        >
          <Plus className="size-3" aria-hidden="true" />
          مدل
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" sideOffset={6} className="w-80 border-2 border-border bg-card p-0 shadow-[6px_6px_0_var(--color-shadow)]" dir="rtl">
        <Command>
          <CommandInput placeholder="جستجوی مدل…" className="font-vazirmatn" />
          <CommandEmpty>مدلی پیدا نشد؛ عبارت دیگری امتحان کنید.</CommandEmpty>
          <CommandList>
            {groups.map(group => (
              <CommandGroup key={group.provider} heading={group.provider}>
                {group.models.map(model => (
                  <CommandItem
                    key={model.id}
                    value={`${model.name} ${model.model_key} ${model.provider}`}
                    onSelect={() => {
                      onAdd(model.id)
                      setOpen(false)
                    }}
                    className="prompt-action cursor-pointer"
                  >
                    <span className="flex-1 truncate" dir="ltr">{model.name}</span>
                    {!model.is_active && (
                      <span className="border border-destructive/60 bg-destructive/10 px-1 py-px text-[10px] font-black text-destructive">منسوخ</span>
                    )}
                  </CommandItem>
                ))}
              </CommandGroup>
            ))}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
