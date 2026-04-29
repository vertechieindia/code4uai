import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import App from '../../App'
import {
  DashboardPage,
  ProjectsPage,
  AgentPage,
  SecurityPage,
  IntegrationsPage,
  DocsPage,
  LoginPage,
  SignupPage,
  ConnectRepoPage,
} from '../../pages'

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }))
})

describe('Smoke tests', () => {
  it('App mounts without errors', () => {
    expect(() => render(<App />)).not.toThrow()
  })

  it('all page components can be imported', () => {
    expect(DashboardPage).toBeDefined()
    expect(ProjectsPage).toBeDefined()
    expect(AgentPage).toBeDefined()
    expect(SecurityPage).toBeDefined()
    expect(IntegrationsPage).toBeDefined()
    expect(DocsPage).toBeDefined()
    expect(LoginPage).toBeDefined()
    expect(SignupPage).toBeDefined()
    expect(ConnectRepoPage).toBeDefined()
  })

  it('Layout renders header and navigation when authenticated', async () => {
    const { setAuthStorage } = await import('../test-utils')
    setAuthStorage('token', { user_id: 'u1', email: 'u@u.com', name: 'User', tenant_id: 't1' })
    const storage = (window as unknown as { __testStorage?: Record<string, string> }).__testStorage
    if (storage) {
      storage['code4u_theme'] = 'dark'
      storage['code4u_tour_completed'] = 'true'
    }

    window.history.replaceState({}, '', '/')
    render(<App />)

    await vi.waitFor(() => {
      expect(screen.getByText('Dashboard')).toBeInTheDocument()
      expect(screen.getByText('Projects')).toBeInTheDocument()
      expect(screen.getByText('AI Agent')).toBeInTheDocument()
      expect(screen.getByText('Security')).toBeInTheDocument()
      expect(screen.getByText('Integrations')).toBeInTheDocument()
      expect(screen.getByText('Docs')).toBeInTheDocument()
    })
  })

  it('dark mode toggle works', async () => {
    const { setAuthStorage } = await import('../test-utils')
    setAuthStorage('token', { user_id: 'u1', email: 'u@u.com', name: 'User', tenant_id: 't1' })
    const storage = (window as unknown as { __testStorage?: Record<string, string> }).__testStorage
    if (storage) {
      storage['code4u_theme'] = 'dark'
      storage['code4u_tour_completed'] = 'true'
    }

    window.history.replaceState({}, '', '/')
    render(<App />)

    await vi.waitFor(() => {
      expect(screen.getByText('Dashboard')).toBeInTheDocument()
    })

    const themeButton = screen.getByTitle('Theme')
    expect(themeButton).toBeInTheDocument()
    themeButton.click()

    await vi.waitFor(() => {
      expect(screen.getByText('Dark')).toBeInTheDocument()
      expect(screen.getByText('Light')).toBeInTheDocument()
      expect(screen.getByText('System')).toBeInTheDocument()
    })
  })
})
