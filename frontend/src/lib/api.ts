const API_BASE = 'http://localhost:8000'

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

export interface ProjectRead { id: number; name: string; description?: string | null; website_url?: string | null; created_at: string; updated_at: string }
export interface ProjectCreate { name: string; description?: string | null; website_url?: string | null }
export interface PromptRead { id: number; project_id: number; text: string; is_active: boolean; created_at: string; updated_at: string; last_run_at?: string | null; models: AIModelRead[] }
export interface AIModelRead { id: number; name: string; provider: string; model_key: string; is_active: boolean; created_at?: string | null }

export function listProjects(): Promise<ProjectRead[]> { return authRequest('GET', '/projects/') }
export function getProject(id: number): Promise<ProjectRead> { return authRequest('GET', '/projects/' + id) }
export function createProject(body: ProjectCreate): Promise<ProjectRead> { return authRequest('POST', '/projects/', body) }
export function deleteProject(id: number): Promise<void> { return authRequest('DELETE', '/projects/' + id) }

export interface PromptCreate { text: string; model_ids?: number[] }
export interface AIRunResult { ai_run_id: number; ai_run_status: string; extraction_status: string; brands_found: number; new_brands: number; existing_brands: number; error_message?: string | null }

export function listPrompts(projectId: number, includeArchived?: boolean): Promise<PromptRead[]> { const qs = includeArchived ? '?include_archived=true' : ''; return authRequest('GET', '/projects/' + projectId + '/prompts' + qs) }
export function createPrompt(projectId: number, body: PromptCreate): Promise<PromptRead> { return authRequest('POST', '/projects/' + projectId + '/prompts', body) }
export function archivePrompt(projectId: number, promptId: number): Promise<void> { return authRequest('DELETE', '/projects/' + projectId + '/prompts/' + promptId) }
export function restorePrompt(projectId: number, promptId: number): Promise<PromptRead> { return authRequest('POST', '/projects/' + projectId + '/prompts/' + promptId + '/restore') }
export function addPromptModel(projectId: number, promptId: number, modelId: number): Promise<void> { return authRequest('POST', '/projects/' + projectId + '/prompts/' + promptId + '/models/' + modelId) }
export function removePromptModel(projectId: number, promptId: number, modelId: number): Promise<void> { return authRequest('DELETE', '/projects/' + projectId + '/prompts/' + promptId + '/models/' + modelId) }
export function runPrompt(projectId: number, promptId: number): Promise<AIRunResult[]> { return authRequest('POST', '/projects/' + projectId + '/prompts/' + promptId + '/run') }

export interface PromptRankingItem { brand: string; domain?: string | null; rank: number; ai_model: string; date: string }
export function getPromptRankings(promptId: number): Promise<PromptRankingItem[]> { return authRequest('GET', '/prompts/' + promptId + '/rankings') }

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
