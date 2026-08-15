import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  type ReactNode,
} from 'react'

import { postJson } from '../shared/api/client'
import type { CurrentUser, RoleName } from '../shared/api/types'

type LoginPayload = { username: string; password: string }

type AuthState = {
  user: CurrentUser | null
  status: 'loading' | 'authenticated' | 'anonymous'
  login: (payload: LoginPayload) => Promise<CurrentUser>
  logout: () => Promise<void>
  hasRole: (...roles: RoleName[]) => boolean
}

const AuthContext = createContext<AuthState | null>(null)

async function fetchCurrentUser(): Promise<CurrentUser | null> {
  const response = await fetch('/api/v1/auth/me', {
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (response.status === 401) {
    return null
  }
  if (!response.ok) {
    throw new Error('无法获取当前会话')
  }
  return (await response.json()) as CurrentUser
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const me = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: fetchCurrentUser,
    retry: false,
    staleTime: 60_000,
  })

  const loginMutation = useMutation({
    mutationFn: (payload: LoginPayload) =>
      postJson<{ user: CurrentUser }>('/api/v1/auth/login', payload),
    onSuccess: (data) => {
      queryClient.setQueryData(['auth', 'me'], data.user)
    },
  })

  const logoutMutation = useMutation({
    mutationFn: () => postJson<void>('/api/v1/auth/logout'),
    onSuccess: () => {
      queryClient.setQueryData(['auth', 'me'], null)
      queryClient.clear()
    },
  })

  const login = useCallback(
    async (payload: LoginPayload): Promise<CurrentUser> => {
      const data = await loginMutation.mutateAsync(payload)
      return data.user
    },
    [loginMutation],
  )

  const logout = useCallback(async () => {
    await logoutMutation.mutateAsync()
  }, [logoutMutation])

  const user = me.data ?? null
  const status: AuthState['status'] = me.isPending
    ? 'loading'
    : user
      ? 'authenticated'
      : 'anonymous'

  const value = useMemo<AuthState>(
    () => ({
      user,
      status,
      login,
      logout,
      hasRole: (...roles: RoleName[]) =>
        user !== null && roles.some((role) => user.roles.includes(role)),
    }),
    [user, status, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext)
  if (context === null) {
    throw new Error('useAuth must be used inside AuthProvider')
  }
  return context
}
