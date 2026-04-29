import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'

interface AuthUser {
  user_id: string
  email: string
  name: string
  tenant_id: string
}

interface AuthContextType {
  user: AuthUser | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (email: string, password: string) => Promise<{ ok: boolean; error?: string }>
  register: (email: string, password: string, name: string, company?: string) => Promise<{ ok: boolean; error?: string }>
  logout: () => void
}

const AuthContext = createContext<AuthContextType | null>(null)

const TOKEN_KEY = 'code4u_token'
const USER_KEY = 'code4u_user'

const PUBLIC_PATHS = ['/login', '/signup']

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(() => {
    const stored = localStorage.getItem(USER_KEY)
    return stored ? JSON.parse(stored) : null
  })
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY))
  const [isLoading, setIsLoading] = useState(false)

  const isAuthenticated = !!token && !!user

  const persistAuth = (tok: string, usr: AuthUser) => {
    localStorage.setItem(TOKEN_KEY, tok)
    localStorage.setItem(USER_KEY, JSON.stringify(usr))
    setToken(tok)
    setUser(usr)
  }

  const clearAuth = () => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    setToken(null)
    setUser(null)
  }

  const login = async (email: string, password: string): Promise<{ ok: boolean; error?: string }> => {
    setIsLoading(true)
    try {
      const res = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        return { ok: false, error: data.detail || 'Login failed' }
      }
      const data = await res.json()
      persistAuth(data.token, {
        user_id: data.user_id,
        email: data.email,
        name: data.name,
        tenant_id: data.tenant_id,
      })
      return { ok: true }
    } catch {
      return { ok: false, error: 'Network error — is the backend running?' }
    } finally {
      setIsLoading(false)
    }
  }

  const register = async (
    email: string,
    password: string,
    name: string,
    company?: string,
  ): Promise<{ ok: boolean; error?: string }> => {
    setIsLoading(true)
    try {
      const res = await fetch('/api/v1/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, name, company: company || '' }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        return { ok: false, error: data.detail || 'Registration failed' }
      }
      const data = await res.json()
      persistAuth(data.token, {
        user_id: data.user_id,
        email: data.email,
        name: data.name,
        tenant_id: data.tenant_id,
      })
      return { ok: true }
    } catch {
      return { ok: false, error: 'Network error — is the backend running?' }
    } finally {
      setIsLoading(false)
    }
  }

  const logout = () => {
    clearAuth()
  }

  return (
    <AuthContext.Provider value={{ user, token, isAuthenticated, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    if (!isAuthenticated && !PUBLIC_PATHS.includes(location.pathname)) {
      navigate('/login', { replace: true })
    }
  }, [isAuthenticated, location.pathname, navigate])

  if (!isAuthenticated && !PUBLIC_PATHS.includes(location.pathname)) {
    return null
  }

  return <>{children}</>
}
