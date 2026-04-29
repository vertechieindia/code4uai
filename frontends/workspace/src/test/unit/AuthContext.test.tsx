import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider, useAuth, RequireAuth } from '../../AuthContext'

// Mock fetch before any imports that use it
const mockFetch = vi.fn()
beforeEach(() => {
  vi.stubGlobal('fetch', mockFetch)
  mockFetch.mockReset()
})

function TestChild() {
  const { user, isAuthenticated, login, logout, register } = useAuth()
  return (
    <div>
      <span data-testid="user">{user?.email ?? 'none'}</span>
      <span data-testid="authenticated">{String(isAuthenticated)}</span>
      <button onClick={() => login('test@test.com', 'pass')}>Login</button>
      <button onClick={() => register('a@b.com', 'pass', 'Name')}>Register</button>
      <button onClick={logout}>Logout</button>
    </div>
  )
}

describe('AuthContext', () => {
  it('AuthProvider renders children', () => {
    render(
      <MemoryRouter>
        <AuthProvider>
          <div data-testid="child">Child content</div>
        </AuthProvider>
      </MemoryRouter>
    )
    expect(screen.getByTestId('child')).toHaveTextContent('Child content')
  })

  it('useAuth provides login, logout, register functions', () => {
    render(
      <MemoryRouter>
        <AuthProvider>
          <TestChild />
        </AuthProvider>
      </MemoryRouter>
    )
    expect(screen.getByRole('button', { name: /login/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /register/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /logout/i })).toBeInTheDocument()
  })

  it('Login stores token in localStorage', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        token: 'fake-token-123',
        user_id: 'u1',
        email: 'test@test.com',
        name: 'Test User',
        tenant_id: 't1',
      }),
    })

    render(
      <MemoryRouter>
        <AuthProvider>
          <TestChild />
        </AuthProvider>
      </MemoryRouter>
    )

    fireEvent.click(screen.getByRole('button', { name: /login/i }))

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v1/auth/login',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ email: 'test@test.com', password: 'pass' }),
        })
      )
    })

    await waitFor(() => {
      expect(localStorage.setItem).toHaveBeenCalledWith('code4u_token', 'fake-token-123')
      expect(localStorage.setItem).toHaveBeenCalledWith(
        'code4u_user',
        expect.stringContaining('test@test.com')
      )
    })
  })

  it('Logout clears user state', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        token: 'token',
        user_id: 'u1',
        email: 'u@u.com',
        name: 'User',
        tenant_id: 't1',
      }),
    })

    render(
      <MemoryRouter>
        <AuthProvider>
          <TestChild />
        </AuthProvider>
      </MemoryRouter>
    )

    fireEvent.click(screen.getByRole('button', { name: /login/i }))
    await waitFor(() => expect(screen.getByTestId('authenticated')).toHaveTextContent('true'))

    fireEvent.click(screen.getByRole('button', { name: /logout/i }))

    await waitFor(() => {
      expect(localStorage.removeItem).toHaveBeenCalledWith('code4u_token')
      expect(localStorage.removeItem).toHaveBeenCalledWith('code4u_user')
    })
    expect(screen.getByTestId('authenticated')).toHaveTextContent('false')
  })

  it('RequireAuth redirects to /login when not authenticated', async () => {
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <AuthProvider>
          <Routes>
            <Route
              path="/dashboard"
              element={
                <RequireAuth>
                  <div data-testid="protected">Protected</div>
                </RequireAuth>
              }
            />
            <Route path="/login" element={<div data-testid="login">Login Page</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.queryByTestId('protected')).not.toBeInTheDocument()
      expect(screen.getByTestId('login')).toHaveTextContent('Login Page')
    })
  })

  it('RequireAuth renders children when authenticated', async () => {
    const { setAuthStorage } = await import('../test-utils')
    setAuthStorage('existing-token', { user_id: 'u1', email: 'u@u.com', name: 'User', tenant_id: 't1' })

    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <AuthProvider>
          <Routes>
            <Route
              path="/dashboard"
              element={
                <RequireAuth>
                  <div data-testid="protected">Protected Content</div>
                </RequireAuth>
              }
            />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByTestId('protected')).toHaveTextContent('Protected Content')
    })
  })
})
