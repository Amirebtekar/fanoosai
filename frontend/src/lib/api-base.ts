export function getApiBaseUrl(configuredUrl?: string): string {
  const fallback = typeof window !== 'undefined' ? window.location.origin : ''
  const baseUrl = configuredUrl?.trim() || fallback
  return baseUrl.replace(/\/+$/, '')
}
