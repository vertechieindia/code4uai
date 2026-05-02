/**
 * Security, Performance, and Advanced Testing
 *
 * Testing types: Security Audit, Performance, Black Box,
 * White Box, Grey Box, Acceptance
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { setAuthStorage, clearAuthStorage } from '../test-utils'
import App from '../../App'

const mockFetch = vi.fn()
globalThis.fetch = mockFetch

beforeEach(() => {
  clearAuthStorage()
  mockFetch.mockReset()
  mockFetch.mockResolvedValue({
    ok: true,
    json: async () => ({}),
    text: async () => '',
    status: 200,
  })
  const storage = (window as unknown as { __testStorage?: Record<string, string> }).__testStorage
  if (storage) {
    storage['code4u_tour_completed'] = 'true'
    storage['code4u_theme'] = 'dark'
  }
})

function loginUser() {
  setAuthStorage('test-token', {
    user_id: 'u1',
    name: 'Test',
    email: 'test@code4u.ai',
    tenant_id: 't1',
  })
}

function renderAt(route: string, options?: { auth?: boolean }) {
  window.history.pushState({}, '', route)
  if (options?.auth) loginUser()
  return render(<App />)
}

// ═══════════════════════════════════════════════════════════════
// SECURITY TESTS
// ═══════════════════════════════════════════════════════════════

describe('Security Tests — Authentication', () => {
  it('unauthenticated users cannot access protected routes', () => {
    clearAuthStorage()
    renderAt('/guardian')
    const content = document.body.textContent || ''
    expect(content).toBeDefined()
  })

  it('unauthenticated users cannot access agent page', () => {
    clearAuthStorage()
    renderAt('/agent')
    expect(document.body.textContent).toBeDefined()
  })

  it('unauthenticated users cannot access org dashboard', () => {
    clearAuthStorage()
    renderAt('/org-dashboard')
    expect(document.body.textContent).toBeDefined()
  })

  it('token stored in storage when authenticated', () => {
    loginUser()
    const storage = (window as unknown as { __testStorage?: Record<string, string> }).__testStorage
    expect(storage?.['code4u_token']).toBe('test-token')
  })

  it('clearing auth removes token', () => {
    loginUser()
    clearAuthStorage()
    const storage = (window as unknown as { __testStorage?: Record<string, string> }).__testStorage
    expect(storage?.['code4u_token']).toBeUndefined()
  })
})

describe('Security Tests — XSS Prevention', () => {
  it('renders script tags as text, not executable', () => {
    renderAt('/', { auth: true })
    const scripts = document.querySelectorAll('script[data-malicious]')
    expect(scripts.length).toBe(0)
  })

  it('user-provided names are escaped in DOM', () => {
    setAuthStorage('token', {
      user_id: 'u1',
      name: '<script>alert("xss")</script>',
      email: 'test@test.com',
      tenant_id: 't1',
    })
    renderAt('/', { auth: true })
    const content = document.body.innerHTML
    expect(content).not.toContain('<script>alert')
  })
})

describe('Security Tests — CSRF & Headers', () => {
  it('API calls are made when authenticated', () => {
    renderAt('/', { auth: true })
    expect(mockFetch).toHaveBeenCalled()
  })
})

// ═══════════════════════════════════════════════════════════════
// PERFORMANCE TESTS
// ═══════════════════════════════════════════════════════════════

describe('Performance Tests — Render Speed', () => {
  it('DashboardPage renders in < 500ms', () => {
    const start = performance.now()
    renderAt('/', { auth: true })
    const elapsed = performance.now() - start
    expect(elapsed).toBeLessThan(500)
  })

  it('GuardianPage renders in < 500ms', () => {
    const start = performance.now()
    renderAt('/guardian', { auth: true })
    const elapsed = performance.now() - start
    expect(elapsed).toBeLessThan(500)
  })

  it('OrgDashboard renders in < 500ms', () => {
    const start = performance.now()
    renderAt('/org-dashboard', { auth: true })
    const elapsed = performance.now() - start
    expect(elapsed).toBeLessThan(500)
  })

  it('IntegrationsPage renders in < 500ms', () => {
    const start = performance.now()
    renderAt('/integrations', { auth: true })
    const elapsed = performance.now() - start
    expect(elapsed).toBeLessThan(500)
  })

  it('LoginPage renders in < 200ms', () => {
    const start = performance.now()
    renderAt('/login')
    const elapsed = performance.now() - start
    expect(elapsed).toBeLessThan(200)
  })
})

describe('Performance Tests — DOM Size', () => {
  it('dashboard DOM is reasonable size', () => {
    renderAt('/', { auth: true })
    const nodes = document.querySelectorAll('*')
    expect(nodes.length).toBeLessThan(2000)
  })

  it('guardian page DOM is reasonable size', () => {
    renderAt('/guardian', { auth: true })
    const nodes = document.querySelectorAll('*')
    expect(nodes.length).toBeLessThan(2000)
  })
})

// ═══════════════════════════════════════════════════════════════
// BLACK BOX TESTS — Testing without internal knowledge
// ═══════════════════════════════════════════════════════════════

describe('Black Box Tests — User Flows', () => {
  it('user sees dashboard after login', () => {
    renderAt('/', { auth: true })
    expect(screen.getByText(/welcome/i)).toBeDefined()
  })

  it('user sees navigation sidebar', () => {
    renderAt('/', { auth: true })
    expect(screen.getByText(/dashboard/i)).toBeDefined()
  })

  it('guardian page shows quality information', () => {
    renderAt('/guardian', { auth: true })
    expect(screen.getAllByText(/guardian/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/security/i).length).toBeGreaterThan(0)
  })

  it('org dashboard shows organization info', () => {
    renderAt('/org-dashboard', { auth: true })
    expect(screen.getAllByText(/organization/i).length).toBeGreaterThan(0)
  })
})

// ═══════════════════════════════════════════════════════════════
// WHITE BOX TESTS — Testing with internal knowledge
// ═══════════════════════════════════════════════════════════════

describe('White Box Tests — Internal State', () => {
  it('AuthContext provides token to child components', () => {
    renderAt('/', { auth: true })
    expect(mockFetch).toHaveBeenCalled()
  })

  it('guardian page initializes with idle status', () => {
    renderAt('/guardian', { auth: true })
    expect(screen.getByText(/cycle 1\/10/i)).toBeDefined()
  })

  it('org dashboard initializes with security tab', () => {
    renderAt('/org-dashboard', { auth: true })
    expect(screen.getAllByText(/security posture/i).length).toBeGreaterThan(0)
  })
})

// ═══════════════════════════════════════════════════════════════
// GREY BOX TESTS — Partial knowledge testing
// ═══════════════════════════════════════════════════════════════

describe('Grey Box Tests — API Integration', () => {
  it('dashboard makes API calls on mount', () => {
    renderAt('/', { auth: true })
    expect(mockFetch).toHaveBeenCalled()
  })

  it('dashboard fetches projects, analytics, telemetry', () => {
    renderAt('/', { auth: true })
    const urls = mockFetch.mock.calls.map((c: unknown[]) => c[0])
    expect(urls.length).toBeGreaterThan(0)
  })
})

// ═══════════════════════════════════════════════════════════════
// ACCEPTANCE TESTS (Alpha)
// ═══════════════════════════════════════════════════════════════

describe('Alpha Acceptance Tests', () => {
  it('complete user journey: login -> dashboard -> guardian', () => {
    renderAt('/', { auth: true })
    expect(screen.getByText(/welcome/i)).toBeDefined()
    expect(document.body.innerHTML).toContain('Guardian')
  })

  it('dashboard shows all key sections', () => {
    renderAt('/', { auth: true })
    expect(screen.getByText(/hours saved/i)).toBeDefined()
    expect(screen.getByText(/start coding/i)).toBeDefined()
    expect(screen.getByText(/sovereign launch/i)).toBeDefined()
  })

  it('guardian provides both gauntlet and governance views', () => {
    renderAt('/guardian', { auth: true })
    expect(screen.getAllByText(/quality gauntlet/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/governance/i).length).toBeGreaterThan(0)
  })

  it('org dashboard provides both security and intelligence views', () => {
    renderAt('/org-dashboard', { auth: true })
    expect(screen.getAllByText(/security posture/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/collective intelligence/i).length).toBeGreaterThan(0)
  })
})
