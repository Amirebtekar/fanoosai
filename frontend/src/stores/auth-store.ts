import { create } from 'zustand'

interface UserInfo {
  id: number
  email: string | null
  first_name?: string | null
  last_name?: string | null
  phone?: string | null
  is_active: boolean
  is_superuser: boolean
  is_verified: boolean
}

interface AuthState {
  user: UserInfo | null
  setUser: (user: UserInfo | null) => void
  getToken: () => string | null
  setToken: (token: string) => void
  clearAuth: () => void
  isAuthenticated: () => boolean
}

export const useAuthStore = create<AuthState>()((set) => ({
  user: (() => {
    try { const raw = localStorage.getItem('user'); return raw ? JSON.parse(raw) : null }
    catch { return null }
  })(),
  setUser: (user) => {
    if (user) localStorage.setItem('user', JSON.stringify(user))
    else localStorage.removeItem('user')
    set({ user })
  },
  getToken: () => localStorage.getItem('access_token'),
  setToken: (token) => localStorage.setItem('access_token', token),
  clearAuth: () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('user')
    set({ user: null })
  },
  isAuthenticated: () => !!localStorage.getItem('access_token'),
}))
