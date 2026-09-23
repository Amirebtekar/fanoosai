import type { AIModelRead } from '@/lib/api'

export function modelMatches(model: AIModelRead, query: string): boolean {
  const q = query.trim().toLowerCase()
  if (!q) return true
  return [model.name, model.model_key, model.provider].some(value => (value || '').toLowerCase().includes(q))
}

export function filterModels(models: AIModelRead[], query: string): AIModelRead[] {
  return models.filter(model => modelMatches(model, query))
}

export function providerOf(model: AIModelRead): string {
  const raw = (model.provider || '').trim()
  if (raw && raw.toLowerCase() !== 'gateway') return raw
  const slash = model.model_key.indexOf('/')
  return slash > 0 ? model.model_key.slice(0, slash) : 'سایر'
}

export function groupModelsByProvider(models: AIModelRead[]): Array<{ provider: string; models: AIModelRead[] }> {
  const map = new Map<string, AIModelRead[]>()
  for (const model of models) {
    const key = providerOf(model)
    const list = map.get(key)
    if (list) list.push(model)
    else map.set(key, [model])
  }
  return [...map.entries()]
    .map(([provider, list]) => ({
      provider,
      models: [...list].sort((a, b) => a.name.localeCompare(b.name, 'en')),
    }))
    .sort((a, b) => a.provider.localeCompare(b.provider, 'en'))
}
