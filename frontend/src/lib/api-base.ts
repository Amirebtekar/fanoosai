export function getApiBaseUrl(configuredUrl?: string): string {
  const baseUrl = configuredUrl?.trim() || window.location.origin
  return baseUrl.replace(/\/+$/, '')
}