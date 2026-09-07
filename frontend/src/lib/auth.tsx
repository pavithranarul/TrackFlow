import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api, tokens } from './api'
import { useMe } from './queries'
import type { User } from './types'

interface AuthValue {
  user: User | null
  loading: boolean
  signIn: (username: string, password: string) => Promise<void>
  register: (payload: RegisterPayload) => Promise<void>
  signOut: () => void
}

export interface RegisterPayload {
  username: string
  email: string
  password: string
  password_confirm: string
  first_name?: string
  last_name?: string
}

const AuthContext = createContext<AuthValue>(null as unknown as AuthValue)

export const useAuth = () => useContext(AuthContext)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [hasToken, setHasToken] = useState(() => Boolean(tokens.access))
  const queryClient = useQueryClient()

  const { data: user, isLoading, isError } = useMe(hasToken)

  // The api layer fires this when a refresh fails, so an expired session
  // drops the user back to the sign-in screen instead of looping on 401s.
  useEffect(() => {
    const onSignedOut = () => {
      setHasToken(false)
      queryClient.clear()
    }
    window.addEventListener('trackflow:signed-out', onSignedOut)
    return () => window.removeEventListener('trackflow:signed-out', onSignedOut)
  }, [queryClient])

  useEffect(() => {
    if (isError) {
      tokens.clear()
      setHasToken(false)
    }
  }, [isError])

  const signIn = useCallback(
    async (username: string, password: string) => {
      const data = await api.post<{ access: string; refresh: string }>(
        '/api/auth/login/',
        { username, password },
        true,
      )
      tokens.set(data.access, data.refresh)
      setHasToken(true)
      await queryClient.invalidateQueries()
    },
    [queryClient],
  )

  const register = useCallback(
    async (payload: RegisterPayload) => {
      const data = await api.post<{ access: string; refresh: string }>(
        '/api/auth/register/',
        payload,
        true,
      )
      tokens.set(data.access, data.refresh)
      setHasToken(true)
      await queryClient.invalidateQueries()
    },
    [queryClient],
  )

  const signOut = useCallback(() => {
    tokens.clear()
    setHasToken(false)
    queryClient.clear()
  }, [queryClient])

  const value = useMemo(
    () => ({
      user: hasToken ? (user ?? null) : null,
      loading: hasToken && isLoading,
      signIn,
      register,
      signOut,
    }),
    [hasToken, user, isLoading, signIn, register, signOut],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
