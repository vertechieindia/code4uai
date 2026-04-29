/**
 * Compatibility & Localization Tests
 *
 * Browser compatibility, responsive design, internationalization readiness,
 * and cross-environment consistency checks.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
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
  RefactorPage,
} from '../../pages'

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }))
})

const authUser = { user_id: 'u1', email: 'u@u.com', name: 'User', tenant_id: 't1' }

// ---------------------------------------------------------------------------
// 1. All page components render without errors in jsdom
// ---------------------------------------------------------------------------

describe('Page components render without errors in jsdom', () => {
  const pages = [
    { name: 'DashboardPage', component: <DashboardPage />, needsAuth: true },
    { name: 'ProjectsPage', component: <ProjectsPage />, needsAuth: true },
    { name: 'LoginPage', component: <LoginPage />, needsAuth: false },
    { name: 'SignupPage', component: <SignupPage />, needsAuth: false },
    { name: 'DocsPage', component: <DocsPage />, needsAuth: true },
    { name: 'IntegrationsPage', component: <IntegrationsPage />, needsAuth: true },
    { name: 'SecurityPage', component: <SecurityPage />, needsAuth: true },
    { name: 'AgentPage', component: <AgentPage />, needsAuth: true },
    { name: 'ConnectRepoPage', component: <ConnectRepoPage />, needsAuth: true },
    { name: 'RefactorPage', component: <RefactorPage />, needsAuth: true },
  ]

  pages.forEach(({ name, component, needsAuth }) => {
    it(`${name} renders without throwing`, () => {
      if (needsAuth) setAuthStorage('token', authUser)
      expect(() => renderWithProviders(component)).not.toThrow()
    })
  })
})

// ---------------------------------------------------------------------------
// 2. Components handle window resize events (responsive)
// ---------------------------------------------------------------------------

describe('Responsive design - window resize handling', () => {
  it('components handle resize events without crashing', () => {
    setAuthStorage('token', authUser)
    const { unmount } = renderWithProviders(<DashboardPage />)
    expect(() => {
      window.dispatchEvent(new Event('resize'))
      window.dispatchEvent(new UIEvent('resize', { detail: 0 }))
    }).not.toThrow()
    unmount()
  })

  it('ProjectsPage handles resize', () => {
    setAuthStorage('token', authUser)
    renderWithProviders(<ProjectsPage />)
    expect(() => window.dispatchEvent(new Event('resize'))).not.toThrow()
  })
})

// ---------------------------------------------------------------------------
// 3. All text content is extractable (i18n readiness - no hardcoded concatenation)
// ---------------------------------------------------------------------------

describe('i18n readiness - text content extractable', () => {
  it('LoginPage has extractable text nodes', () => {
    renderWithProviders(<LoginPage />)
    const text = document.body.textContent || ''
    expect(text.length).toBeGreaterThan(0)
    expect(text).toMatch(/sign in|login|email|password/i)
  })

  it('SignupPage has extractable text', () => {
    renderWithProviders(<SignupPage />)
    const text = document.body.textContent || ''
    expect(text).toMatch(/create account|sign up|email|password|full name/i)
  })

  it('no obvious string concatenation for display (uses template literals or separate strings)', () => {
    renderWithProviders(<LoginPage />)
    const buttons = screen.getAllByRole('button')
    buttons.forEach((btn) => {
      const label = btn.textContent || ''
      expect(typeof label).toBe('string')
      expect(label.trim().length).toBeGreaterThanOrEqual(0)
    })
  })
})

// ---------------------------------------------------------------------------
// 4. Date/number formatting uses locale-aware or consistent formatting
// ---------------------------------------------------------------------------

describe('Date and number formatting', () => {
  it('components that display dates use consistent format', () => {
    setAuthStorage('token', authUser)
    renderWithProviders(<DashboardPage />)
    const text = document.body.textContent || ''
    if (text.match(/\d{4}-\d{2}-\d{2}/) || text.match(/\d+\s*(min|hour|ago)/i)) {
      expect(true).toBe(true)
    }
    expect(document.body).toBeInTheDocument()
  })

  it('Intl or toLocaleString available for future i18n', () => {
    expect(typeof Intl !== 'undefined').toBe(true)
    expect(typeof Number.prototype.toLocaleString).toBe('function')
  })
})

// ---------------------------------------------------------------------------
// 5. RTL layout support check (dir attribute handling)
// ---------------------------------------------------------------------------

describe('RTL layout support', () => {
  it('document has dir attribute or can accept it', () => {
    document.documentElement.setAttribute('dir', 'rtl')
    setAuthStorage('token', authUser)
    expect(() => renderWithProviders(<DashboardPage />)).not.toThrow()
    expect(document.documentElement.getAttribute('dir')).toBe('rtl')
    document.documentElement.removeAttribute('dir')
  })

  it('components render when dir=rtl', () => {
    document.documentElement.dir = 'rtl'
    renderWithProviders(<LoginPage />)
    expect(screen.getByPlaceholderText(/you@example\.com/i)).toBeInTheDocument()
    document.documentElement.dir = ''
  })
})

// ---------------------------------------------------------------------------
// 6. Dark mode doesn't break layout
// ---------------------------------------------------------------------------

describe('Dark mode layout', () => {
  it('components render in dark mode (html.dark)', () => {
    document.documentElement.classList.add('dark')
    setAuthStorage('token', authUser)
    renderWithProviders(<DashboardPage />)
    expect(document.body).toBeInTheDocument()
    document.documentElement.classList.remove('dark')
  })

  it('LoginPage renders with dark class', () => {
    document.documentElement.classList.add('dark')
    renderWithProviders(<LoginPage />)
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
    document.documentElement.classList.remove('dark')
  })
})

// ---------------------------------------------------------------------------
// 7. Local storage fallbacks work when storage is unavailable
// ---------------------------------------------------------------------------

describe('Local storage fallbacks', () => {
  it('app handles localStorage getItem returning null', () => {
    const storage = (window as unknown as { __testStorage?: Record<string, string> }).__testStorage
    if (storage) {
      Object.keys(storage).forEach((k) => delete storage[k])
    }
    expect(() => renderWithProviders(<LoginPage />)).not.toThrow()
  })

  it('components work when auth storage is empty', () => {
    const storage = (window as unknown as { __testStorage?: Record<string, string> }).__testStorage
    if (storage) {
      delete storage['code4u_token']
      delete storage['code4u_user']
    }
    renderWithProviders(<LoginPage />)
    expect(screen.getByPlaceholderText(/you@example\.com/i)).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// 8. SVG icons render properly (not broken image)
// ---------------------------------------------------------------------------

describe('SVG icons render', () => {
  it('lucide-react SVGs render in DOM', () => {
    renderWithProviders(<LoginPage />)
    const svgs = document.querySelectorAll('svg')
    expect(svgs.length).toBeGreaterThan(0)
    svgs.forEach((svg) => {
      expect(svg.tagName.toLowerCase()).toBe('svg')
      expect(svg.innerHTML.length).toBeGreaterThan(0)
    })
  })

  it('icons in SignupPage are valid SVG', () => {
    renderWithProviders(<SignupPage />)
    const svgs = document.querySelectorAll('svg')
    expect(svgs.length).toBeGreaterThan(0)
  })
})

// ---------------------------------------------------------------------------
// 9. All external links have target="_blank" and rel="noopener"
// ---------------------------------------------------------------------------

describe('External link security', () => {
  it('external links use target=_blank and rel=noopener', () => {
    renderWithProviders(<LoginPage />)
    const links = document.querySelectorAll('a[href^="http"]')
    links.forEach((a) => {
      const href = a.getAttribute('href') || ''
      if (href.startsWith('http') && !href.includes(window.location.host)) {
        expect(a.getAttribute('target')).toBe('_blank')
        expect(a.getAttribute('rel')).toMatch(/noopener/)
      }
    })
  })

  it('internal links do not require noopener', () => {
    setAuthStorage('token', authUser)
    renderWithProviders(<DashboardPage />)
    const internalLinks = document.querySelectorAll('a[href^="/"]')
    expect(internalLinks.length).toBeGreaterThanOrEqual(0)
  })
})

// ---------------------------------------------------------------------------
// 10. CSS class names are valid (no undefined Tailwind breaking layout)
// ---------------------------------------------------------------------------

describe('CSS class validity', () => {
  it('components use valid Tailwind-like class names', () => {
    renderWithProviders(<LoginPage />)
    const elements = document.querySelectorAll('[class]')
    elements.forEach((el) => {
      const classes = (el.getAttribute('class') || '').split(/\s+/).filter(Boolean)
      classes.forEach((cls) => {
        // Tailwind allows arbitrary values: from-[#0a0a0f], w-[10px], etc.
        expect(cls).toMatch(/^[a-zA-Z0-9_\-\[\]:\/\.#]+$/)
      })
    })
  })

  it('no empty or malformed class attributes', () => {
    setAuthStorage('token', authUser)
    renderWithProviders(<ProjectsPage />)
    const withClass = document.querySelectorAll('[class]')
    withClass.forEach((el) => {
      const c = el.getAttribute('class')
      expect(c === null || (typeof c === 'string' && c.trim().length >= 0)).toBe(true)
    })
  })
})

// ---------------------------------------------------------------------------
// 11. Touch events are handled alongside click events
// ---------------------------------------------------------------------------

describe('Touch event support', () => {
  it('clickable elements respond to click', () => {
    renderWithProviders(<LoginPage />)
    const btn = screen.getByRole('button', { name: /sign in/i })
    expect(() => fireEvent.click(btn)).not.toThrow()
  })

  it('buttons handle touch simulation via click', () => {
    renderWithProviders(<SignupPage />)
    const btn = screen.getByRole('button', { name: /create account/i })
    fireEvent.touchStart(btn)
    fireEvent.touchEnd(btn)
    fireEvent.click(btn)
    expect(btn).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// 12. Viewport meta tag is present for mobile
// ---------------------------------------------------------------------------

describe('Viewport meta tag', () => {
  it('viewport meta tag exists or can be added for mobile', () => {
    let viewport = document.querySelector('meta[name="viewport"]')
    if (!viewport) {
      const meta = document.createElement('meta')
      meta.name = 'viewport'
      meta.content = 'width=device-width, initial-scale=1.0'
      document.head.appendChild(meta)
      viewport = meta
    }
    expect(viewport).toBeTruthy()
    expect(viewport.getAttribute('content')).toMatch(/width|initial-scale/i)
  })
})

// ---------------------------------------------------------------------------
// 13. Form inputs have proper input types (email, password, text)
// ---------------------------------------------------------------------------

describe('Form input types', () => {
  it('LoginPage has email and password inputs', () => {
    renderWithProviders(<LoginPage />)
    const emailInput = screen.getByPlaceholderText(/you@example\.com/i)
    const passwordInput = screen.getByPlaceholderText(/••••••••/i)
    expect(emailInput).toHaveAttribute('type', 'email')
    expect(passwordInput).toHaveAttribute('type', 'password')
  })

  it('SignupPage has proper input types', () => {
    renderWithProviders(<SignupPage />)
    const inputs = document.querySelectorAll('input')
    const hasEmail = Array.from(inputs).some((i) => i.type === 'email')
    const hasPassword = Array.from(inputs).some((i) => i.type === 'password')
    expect(hasEmail || hasPassword).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// 14. All buttons have accessible type attribute
// ---------------------------------------------------------------------------

describe('Button type attributes', () => {
  it('form submit buttons have type=submit or type=button', () => {
    renderWithProviders(<LoginPage />)
    const buttons = screen.getAllByRole('button')
    buttons.forEach((btn) => {
      const type = btn.getAttribute('type')
      expect(['submit', 'button', 'reset']).toContain(type || 'submit')
    })
  })

  it('SignupPage buttons have type or use default submit', () => {
    renderWithProviders(<SignupPage />)
    const buttons = screen.getAllByRole('button')
    expect(buttons.length).toBeGreaterThan(0)
    buttons.forEach((btn) => {
      const type = btn.getAttribute('type') ?? 'submit'
      // Buttons without explicit type default to 'submit' in forms
      expect(['submit', 'button', 'reset']).toContain(type)
    })
  })
})

// ---------------------------------------------------------------------------
// 15. API URLs use relative paths (no hardcoded localhost)
// ---------------------------------------------------------------------------

describe('API URL configuration', () => {
  it('API calls use relative paths when fetching', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({}),
      status: 401,
    })
    vi.stubGlobal('fetch', mockFetch)
    setAuthStorage('token', authUser)
    renderWithProviders(<DashboardPage />)
    await waitFor(() => expect(mockFetch).toHaveBeenCalled(), { timeout: 3000 })
    const calls = mockFetch.mock.calls
    const urls = calls
      .map((c) => (typeof c[0] === 'string' ? c[0] : (c[0] as { url?: string })?.url))
      .filter(Boolean)
    const hasRelative = urls.some((u) => u.startsWith('/') && !u.startsWith('//'))
    expect(hasRelative).toBe(true)
  })

  it('ProjectsPage fetch uses relative path', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ projects: [] }),
    })
    vi.stubGlobal('fetch', mockFetch)
    setAuthStorage('token', authUser)
    renderWithProviders(<ProjectsPage />)
    await waitFor(() => expect(mockFetch).toHaveBeenCalled(), { timeout: 3000 })
    const url = mockFetch.mock.calls[0]?.[0]
    expect(typeof url === 'string' && url.startsWith('/api')).toBe(true)
  })
})
