import { getApiBaseUrl } from './api-base'

const API_BASE = getApiBaseUrl(import.meta.env.VITE_API_BASE_URL)

export interface RegisterBody { phone: string; first_name: string; last_name: string; email?: string | null }
export interface LoginBody { phone: string }
export interface VerifyBody { phone: string; code: string }
export interface UserInfo { id: number; email: string | null; is_active: boolean; is_superuser: boolean; is_verified: boolean; phone?: string | null; first_name?: string | null; last_name?: string | null }
export interface VerifyResponse { success: boolean; access_token?: string; token_type: string; user?: UserInfo | null }

export class ApiError extends Error {
  status: number; detail: unknown
  constructor(status: number, detail: unknown) { super(String(detail)); this.status = status; this.detail = detail }
}

export function getErrorMessage(e: unknown, fallback: string): string {
  if (e instanceof ApiError) {
    const d = e.detail
    if (typeof d === 'string') return d
    if (d && typeof d === 'object' && 'detail' in (d as Record<string, unknown>)) {
      const inner = (d as Record<string, unknown>).detail
      if (typeof inner === 'string') return inner
      if (inner && typeof inner === 'object') {
        if ('reason' in (inner as Record<string, unknown>)) return (inner as Record<string, unknown>).reason as string
        if ('msg' in (inner as Record<string, unknown>)) return (inner as Record<string, unknown>).msg as string
      }
      if (Array.isArray(inner) && inner[0]?.msg) return inner[0].msg
    }
  }
  return fallback
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(API_BASE + path, { method, credentials: 'include', headers: body ? { 'Content-Type': 'application/json' } : undefined, body: body ? JSON.stringify(body) : undefined })
  if (!res.ok) { let detail: unknown; try { detail = await res.json() } catch { detail = res.statusText }; throw new ApiError(res.status, detail) }
  const text = await res.text()
  if (!text) return undefined as T
  return JSON.parse(text)
}

export function registerSms(body: RegisterBody): Promise<unknown> { return request('POST', '/auth/otp/sms/register', body) }
export function requestSms(body: LoginBody): Promise<unknown> { return request('POST', '/auth/otp/sms/request', body) }
export function verifySms(body: VerifyBody): Promise<VerifyResponse> { return request('POST', '/auth/otp/sms/verify', body) }
export function getCurrentUser(): Promise<UserInfo> { return authRequest('GET', '/auth/me') }

function authRequest<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {}
  if (body) headers['Content-Type'] = 'application/json'
  return raw<T>(method, path, headers, body)
}

async function raw<T>(method: string, path: string, headers: Record<string, string>, body?: unknown): Promise<T> {
  const res = await fetch(API_BASE + path, { credentials: 'include', method, headers, body: body ? JSON.stringify(body) : undefined })
  if (!res.ok) {
    let detail: unknown; try { detail = await res.json() } catch { detail = res.statusText }
    if (res.status === 401) { localStorage.removeItem('user'); window.location.href = '/sign-in' }
    throw new ApiError(res.status, detail)
  }
  if (res.status === 204) return undefined as T
  const text = await res.text()
  if (!text) return undefined as T
  return JSON.parse(text)
}

export interface ProjectRead { id: number; name: string; description?: string | null; website_url?: string | null; prompt_count: number; model_count: number; created_at: string; updated_at: string }
export interface ProjectCreate { name: string; description?: string | null; website_url: string; brand_name: string }
export interface ProjectUpdate { name?: string; description?: string | null; website_url?: string }
export interface PromptRead { id: number; project_id: number; text: string; is_active: boolean; created_at: string; updated_at: string; last_run_at?: string | null; models: AIModelRead[] }
export interface AIModelRead { id: number; name: string; provider: string; model_key: string; is_active: boolean; created_at?: string | null }

export function listProjects(): Promise<ProjectRead[]> { return authRequest('GET', '/projects/') }
export function getProject(id: number): Promise<ProjectRead> { return authRequest('GET', '/projects/' + id) }
export function createProject(body: ProjectCreate): Promise<ProjectRead> { return authRequest('POST', '/projects/', body) }
export function updateProject(id: number, body: ProjectUpdate): Promise<ProjectRead> { return authRequest('PUT', '/projects/' + id, body) }
export function deleteProject(id: number): Promise<void> { return authRequest('DELETE', '/projects/' + id) }

export interface PromptCreate { text: string; model_ids: number[] }
export interface AIRunResult { ai_run_id: number; ai_run_status: string; extraction_status: string; brands_found: number; new_brands: number; existing_brands: number; error_message?: string | null }
export interface PromptModelExecutionAvailability { model_id: number; model_name: string; can_run: boolean; claim_source?: string | null }
export interface ProjectRun { ai_run_id: number; prompt: string; ai_model: string; status: string; extraction_status: string; created_at: string; completed_at?: string | null }
export interface Page<T> { items: T[]; page: number; page_size: number; total: number }
export interface ProjectBrand { id: number; name: string; domain?: string | null; kind: 'owned' | 'competitor'; brand_id?: number | null }
export interface ObservedBrand { brand_id: number; name: string; domain: string }
export interface ProjectDashboard { visibility: number; average_rank?: number | null; appearances: number; last_successful_run?: string | null; competitors: { name: string; appearances: number; average_rank?: number | null }[] }
export interface ModelPerformance { ai_model: string; total_runs: number; successful_runs: number; direct_successful_runs: number; fallback_successful_runs: number; failed_runs: number; success_rate: number }
export interface AlertItem { id: number; kind: string; message: string; read_at?: string | null; created_at: string }

export function listPrompts(projectId: number, includeArchived?: boolean): Promise<PromptRead[]> { const qs = includeArchived ? '?include_archived=true' : ''; return authRequest('GET', '/projects/' + projectId + '/prompts' + qs) }
export function createPrompt(projectId: number, body: PromptCreate): Promise<PromptRead> { return authRequest('POST', '/projects/' + projectId + '/prompts', body) }
export function archivePrompt(projectId: number, promptId: number): Promise<void> { return authRequest('DELETE', '/projects/' + projectId + '/prompts/' + promptId) }
export function restorePrompt(projectId: number, promptId: number): Promise<PromptRead> { return authRequest('POST', '/projects/' + projectId + '/prompts/' + promptId + '/restore') }
export function addPromptModel(projectId: number, promptId: number, modelId: number): Promise<void> { return authRequest('POST', '/projects/' + projectId + '/prompts/' + promptId + '/models/' + modelId) }
export function removePromptModel(projectId: number, promptId: number, modelId: number): Promise<void> { return authRequest('DELETE', '/projects/' + projectId + '/prompts/' + promptId + '/models/' + modelId) }
export function runPrompt(projectId: number, promptId: number): Promise<AIRunResult[]> { return authRequest('POST', '/projects/' + projectId + '/prompts/' + promptId + '/run') }
export function getExecutionAvailability(projectId: number, promptId: number): Promise<PromptModelExecutionAvailability[]> { return authRequest('GET', '/projects/' + projectId + '/prompts/' + promptId + '/execution-availability') }
export function getProjectRuns(projectId: number, page = 1): Promise<Page<ProjectRun>> { return authRequest('GET', '/projects/' + projectId + '/runs?page=' + page) }
export function listProjectBrands(projectId: number): Promise<ProjectBrand[]> { return authRequest('GET', '/projects/' + projectId + '/brands') }
export function listObservedBrands(projectId: number): Promise<ObservedBrand[]> { return authRequest('GET', '/projects/' + projectId + '/observed-brands') }
export function addProjectBrand(projectId: number, body: Omit<ProjectBrand, 'id' | 'brand_id'>): Promise<ProjectBrand> { return authRequest('POST', '/projects/' + projectId + '/brands', body) }
export function deleteProjectBrand(projectId: number, brandId: number): Promise<void> { return authRequest('DELETE', '/projects/' + projectId + '/brands/' + brandId) }
export function getProjectDashboard(projectId: number): Promise<ProjectDashboard> { return authRequest('GET', '/projects/' + projectId + '/dashboard') }
export function getModelPerformance(projectId: number): Promise<ModelPerformance[]> { return authRequest('GET', '/projects/' + projectId + '/model-performance') }
export function listAlerts(projectId: number): Promise<AlertItem[]> { return authRequest('GET', '/projects/' + projectId + '/alerts') }
export function addAlertRule(projectId: number, kind: string, cooldown_hours = 24): Promise<unknown> { return authRequest('POST', `/projects/${projectId}/alert-rules?kind=${kind}&cooldown_hours=${cooldown_hours}`) }
export function readAlert(projectId: number, alertId: number): Promise<void> { return authRequest('POST', `/projects/${projectId}/alerts/${alertId}/read`) }
export function exportRunsCsv(projectId: number): void { window.open(`${API_BASE}/projects/${projectId}/runs.csv`, '_blank', 'noopener') }
export function createReportShare(projectId: number): Promise<{ token: string; expires_at: string }> { return authRequest('POST', `/projects/${projectId}/shares`) }
export interface SharedReport { runs: { model: string; status: string; created_at: string }[] }
export function getReportShareUrl(token: string): string { return `${window.location.origin}/shared/${encodeURIComponent(token)}` }
export function getSharedReport(token: string): Promise<SharedReport> { return request('GET', `/shared/${encodeURIComponent(token)}`) }
export function revokeReportShare(projectId: number, token: string): Promise<void> { return authRequest('DELETE', `/projects/${projectId}/shares/${token}`) }
export function listAdminModels(): Promise<AIModelRead[]> { return authRequest('GET', '/ai-models/admin') }
export function setModelActive(id: number, is_active: boolean): Promise<AIModelRead> { return authRequest('PATCH', `/ai-models/${id}?is_active=${is_active}`) }

export interface PromptRankingItem { brand: string; domain?: string | null; rank: number; ai_model: string; date: string }
export interface LatestRanking extends PromptRankingItem { confidence?: number | null }
export function getPromptRankings(promptId: number): Promise<PromptRankingItem[]> { return authRequest('GET', '/prompts/' + promptId + '/rankings') }
export function getLatestRankings(promptId: number, params: { page?: number; ai_model_id?: number; brand_id?: number; start_date?: string; end_date?: string; sort?: 'rank' | 'date' } = {}): Promise<Page<LatestRanking>> { const query = new URLSearchParams(); Object.entries(params).forEach(([key, value]) => { if (value !== undefined) query.set(key, String(value)) }); return authRequest('GET', `/prompts/${promptId}/latest-rankings?${query}`) }

export interface BrandTrendPoint { date: string; rank: number; ai_run_id: number }
export interface BrandTrend { brand_id: number; brand: string; domain?: string | null; ai_model_id: number; ai_model: string; points: BrandTrendPoint[]; rank_change?: number | null; trend: 'up' | 'down' | 'flat' }
export interface PromptBrandTrends { prompt_id: number; items: BrandTrend[] }
export function getPromptBrandTrends(promptId: number, params?: { ai_model_id?: number; brand_ids?: number[]; start_date?: string; end_date?: string }): Promise<PromptBrandTrends> {
  const query = new URLSearchParams()
  if (params?.ai_model_id !== undefined) query.set('ai_model_id', String(params.ai_model_id))
  params?.brand_ids?.forEach((id) => query.append('brand_ids', String(id)))
  if (params?.start_date) query.set('start_date', params.start_date)
  if (params?.end_date) query.set('end_date', params.end_date)
  const suffix = query.toString() ? '?' + query.toString() : ''
  return authRequest('GET', '/prompts/' + promptId + '/brand-trends' + suffix)
}

export interface PromptHistoryItem {
  ai_run_id: number
  ai_model: string
  run_date: string
  request_text: string
  response_text: string | null
  status: string
  extraction_status: string
  brands_count: number
}

export interface PromptHistoryPage { items: PromptHistoryItem[]; page: number; page_size: number; total: number }

export function getPromptHistory(promptId: number, params?: { ai_model_id?: number; start_date?: string; end_date?: string }): Promise<PromptHistoryPage> {
  const query = new URLSearchParams()
  if (params?.ai_model_id !== undefined) query.set('ai_model_id', String(params.ai_model_id))
  if (params?.start_date) query.set('start_date', params.start_date)
  if (params?.end_date) query.set('end_date', params.end_date)
  const suffix = query.toString() ? '?' + query.toString() : ''
  return authRequest('GET', '/prompts/' + promptId + '/history' + suffix)
}

export function listAIModels(): Promise<AIModelRead[]> { return authRequest('GET', '/ai-models') }
export function logout(): Promise<void> { return authRequest('POST', '/auth/jwt/logout') }
