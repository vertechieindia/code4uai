import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { renderWithProviders, setAuthStorage } from '../test-utils'
import {
  DashboardPage,
  ProjectsPage,
  LoginPage,
  SignupPage,
  DocsPage,
  IntegrationsPage,
  SecurityPage,
  AgentPage,
  ConnectRepoPage,
} from '../../pages'

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }))
})

describe('DashboardPage', () => {
  it('renders main sections', async () => {
    setAuthStorage('token', { user_id: 'u1', email: 'u@u.com', name: 'User', tenant_id: 't1' })
    renderWithProviders(<DashboardPage />, { route: '/' })

    expect(screen.getByText(/welcome.*code4u\.ai/i)).toBeInTheDocument()
    expect(screen.getByText(/hours saved/i)).toBeInTheDocument()
    expect(screen.getByText(/recent projects/i)).toBeInTheDocument()
    expect(screen.getByText(/getting started/i)).toBeInTheDocument()
  })
})

describe('ProjectsPage', () => {
  it('renders project list', () => {
    setAuthStorage('token', { user_id: 'u1', email: 'u@u.com', name: 'User', tenant_id: 't1' })
    renderWithProviders(<ProjectsPage />, { route: '/projects' })

    expect(screen.getByText('Projects')).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/search projects/i)).toBeInTheDocument()
  })
})

describe('LoginPage', () => {
  it('renders form fields', () => {
    renderWithProviders(<LoginPage />, { route: '/login' })

    expect(screen.getByPlaceholderText(/you@example\.com/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/••••••••/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
  })
})

describe('SignupPage', () => {
  it('renders registration form', () => {
    renderWithProviders(<SignupPage />, { route: '/signup' })

    expect(screen.getByText(/full name/i)).toBeInTheDocument()
    expect(screen.getByText(/email/i)).toBeInTheDocument()
    expect(screen.getByText(/password/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /create account/i })).toBeInTheDocument()
  })
})

describe('DocsPage', () => {
  it('renders documentation', () => {
    setAuthStorage('token', { user_id: 'u1', email: 'u@u.com', name: 'User', tenant_id: 't1' })
    renderWithProviders(<DocsPage />, { route: '/docs' })

    expect(screen.getByText('Documentation')).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/search documentation/i)).toBeInTheDocument()
    expect(screen.getByText('Getting Started')).toBeInTheDocument()
    expect(screen.getByText('IDE Features')).toBeInTheDocument()
  })
})

describe('SettingsPage (via App)', () => {
  it('renders tabs when navigating to settings', async () => {
    const App = (await import('../../App')).default
    setAuthStorage('token', { user_id: 'u1', email: 'u@u.com', name: 'User', tenant_id: 't1' })
    const storage = (window as unknown as { __testStorage?: Record<string, string> }).__testStorage
    if (storage) {
      storage['code4u_theme'] = 'dark'
      storage['code4u_tour_completed'] = 'true'
    }

    const { userEvent } = await import('@testing-library/user-event')
    render(<App />)

    // Wait for app to load, then click Settings link (icon link to /settings)
    await waitFor(() => {
      const links = screen.getAllByRole('link')
      expect(links.some((l) => l.getAttribute('href') === '/settings')).toBe(true)
    })
    const settingsLink = screen.getAllByRole('link').find((l) => l.getAttribute('href') === '/settings')!
    await userEvent.setup().click(settingsLink)

    await waitFor(() => {
      expect(screen.getByText('Settings')).toBeInTheDocument()
      expect(screen.getByText('Profile')).toBeInTheDocument()
    }, { timeout: 3000 })
  })
})

const authUser = { user_id: 'u1', email: 'u@u.com', name: 'User', tenant_id: 't1' }

describe('All pages render without crashes', () => {
  it('DashboardPage', () => {
    setAuthStorage('token', authUser)
    expect(() => renderWithProviders(<DashboardPage />)).not.toThrow()
  })

  it('ProjectsPage', () => {
    setAuthStorage('token', authUser)
    expect(() => renderWithProviders(<ProjectsPage />)).not.toThrow()
  })

  it('LoginPage', () => {
    expect(() => renderWithProviders(<LoginPage />)).not.toThrow()
  })

  it('SignupPage', () => {
    expect(() => renderWithProviders(<SignupPage />)).not.toThrow()
  })

  it('DocsPage', () => {
    setAuthStorage('token', authUser)
    expect(() => renderWithProviders(<DocsPage />)).not.toThrow()
  })

  it('IntegrationsPage', () => {
    setAuthStorage('token', authUser)
    expect(() => renderWithProviders(<IntegrationsPage />)).not.toThrow()
  })

  it('SecurityPage', () => {
    setAuthStorage('token', authUser)
    expect(() => renderWithProviders(<SecurityPage />)).not.toThrow()
  })

  it('AgentPage', () => {
    setAuthStorage('token', authUser)
    expect(() => renderWithProviders(<AgentPage />)).not.toThrow()
  })

  it('ConnectRepoPage', () => {
    setAuthStorage('token', authUser)
    expect(() => renderWithProviders(<ConnectRepoPage />)).not.toThrow()
  })
})
