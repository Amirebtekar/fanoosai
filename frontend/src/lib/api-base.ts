const LOCAL_API_BASE_URL = 'http://localhost:8000'

export function getApiBaseUrl(configuredUrl?: string): string {
  const baseUrl = configuredUrl?.trim() || LOCAL_API_BASE_URL
  return baseUrl.replace(/\/+$/, '')
}
