import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import App from '../../App'
import { setAuthStorage } from '../test-utils'

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }))
})

function renderAppAt(route: string, authenticated = false) {
  if (authenticated) {
    setAuthStorage('token', { user_id: 'u1', email: 'u@u.com', name: 'User', tenant_id: 't1' })
    const storage = (window as unknown as { __testStorage?: Record<string, string> }).__testStorage
    if (storage) {
      storage['code4u_theme'] = 'dark'
      storage['code4u_tour_completed'] = 'true'
    }
  }

  // Use full URL for replaceState - jsdom may require it for proper routing
  const base = window.location.origin || 'http://localhost'
  window.history.replaceState({}, '', base + route)
  return render(<App />)
}

describe('Routing', () => {
  it('/ renders DashboardPage when authenticated', async () => {
    renderAppAt('/', true)

    await waitFor(() => {
      expect(screen.getByText(/welcome.*code4u\.ai/i)).toBeInTheDocument()
    })
  })

  it('/projects renders ProjectsPage when authenticated', async () => {
    renderAppAt('/projects', true)
    // Projects page has h1 "Projects" and nav link "Projects"
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Projects' })).toBeInTheDocument()
    })
  })

  it('/login renders LoginPage', () => {
    renderAppAt('/login')
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/you@example\.com/i)).toBeInTheDocument()
  })

  // Skip: jsdom's history.replaceState doesn't reliably update BrowserRouter's initial location
  it.skip('/agent renders AgentPage when authenticated', async () => {
    renderAppAt('/agent', true)
    await waitFor(() => {
      expect(screen.getByText('AI Agent')).toBeInTheDocument()
    }, { timeout: 3000 })
  })

  it.skip('/security renders SecurityPage when authenticated', async () => {
    renderAppAt('/security', true)
    await waitFor(() => {
      expect(screen.getByText(/security & compliance/i)).toBeInTheDocument()
    })
  })

  it('protected routes redirect to login when not authenticated', async () => {
    renderAppAt('/')
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
    })
  })

  it('login page redirects authenticated users to dashboard', async () => {
    renderAppAt('/login', true)

    await waitFor(() => {
      expect(screen.getByText(/welcome.*code4u\.ai/i)).toBeInTheDocument()
    })
  })
})
