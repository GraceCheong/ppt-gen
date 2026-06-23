import { create } from 'zustand'
import { fetchMe, apiLogin, apiSignup, apiLogout, type UserInfo } from '../api/auth'

/**
 * loading: 세션 확인 중
 * unauthenticated: 비로그인, 로그인/회원가입/Guest 선택 화면
 * guest: Guest Mode 선택
 * user: 로그인됨
 */
type AuthMode = 'loading' | 'unauthenticated' | 'guest' | 'user'

interface AuthState {
  mode: AuthMode
  user: UserInfo | null
  checkSession: () => Promise<void>
  login: (id: string, pw: string) => Promise<void>
  signup: (payload: { church: string; nickname: string; id: string; pw: string }) => Promise<void>
  logout: () => Promise<void>
  enterGuestMode: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  mode: 'loading',
  user: null,

  checkSession: async () => {
    try {
      const res = await fetchMe()
      if (res.mode === 'user' && res.user) {
        set({ mode: 'user', user: res.user })
      } else {
        set({ mode: 'unauthenticated', user: null })
      }
    } catch {
      set({ mode: 'unauthenticated', user: null })
    }
  },

  login: async (id, pw) => {
    const user = await apiLogin(id, pw)
    set({ mode: 'user', user })
  },

  signup: async (payload) => {
    const user = await apiSignup(payload)
    set({ mode: 'user', user })
  },

  logout: async () => {
    await apiLogout()
    set({ mode: 'unauthenticated', user: null })
  },

  enterGuestMode: () => {
    set({ mode: 'guest', user: null })
  },
}))
