import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { renderWithProviders, setAuthStorage } from '../test-utils'
import App from '../../App'
import IntegrationsPage from '../../pages/IntegrationsPage'

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }))
})

describe('Regression tests', () => {
  it('tour does not show after completion', () => {
    setAuthStorage('token', { user_id: 'u1', email: 'u@u.com', name: 'User', tenant_id: 't1' })
    const storage = (window as unknown as { __testStorage?: Record<string, string> }).__testStorage
    if (storage) {
      storage['code4u_tour_completed'] = 'true'
      storage['code4u_theme'] = 'dark'
    }

    window.history.replaceState({}, '', '/')
    render(<App />)

    // Tour should not be visible when code4u_tour_completed is set
    expect(screen.queryByText(/step 1 of/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/skip tour/i)).not.toBeInTheDocument()
  })

  it('auth state persists across components', async () => {
    setAuthStorage('token', { user_id: 'u1', email: 'u@u.com', name: 'User', tenant_id: 't1' })

    renderWithProviders(<IntegrationsPage />, { route: '/integrations' })

    // Should render authenticated content (Integrations page, not login)
    expect(screen.getByText('Integrations')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /sign in/i })).not.toBeInTheDocument()
  })

  it('navigation updates URL and renders correct page', async () => {
    setAuthStorage('token', { user_id: 'u1', email: 'u@u.com', name: 'User', tenant_id: 't1' })
    const storage = (window as unknown as { __testStorage?: Record<string, string> }).__testStorage
    if (storage) {
      storage['code4u_theme'] = 'dark'
      storage['code4u_tour_completed'] = 'true'
    }

    window.history.replaceState({}, '', '/')
    const { getByRole } = render(<App />)

    await waitFor(() => {
      expect(screen.getByText(/welcome.*code4u\.ai/i)).toBeInTheDocument()
    })

    const projectsLink = screen.getByRole('link', { name: 'Projects' })
    projectsLink.click()

    await waitFor(() => {
      expect(screen.getByText('Projects')).toBeInTheDocument()
      expect(window.location.pathname).toBe('/projects')
    })
  })

  it('integration logos have src attributes', () => {
    setAuthStorage('token', { user_id: 'u1', email: 'u@u.com', name: 'User', tenant_id: 't1' })

    renderWithProviders(<IntegrationsPage />, { route: '/integrations' })

    // Integrations with logo images (not the vscode SVG placeholder)
    const images = screen.getAllByRole('img')
    const integrationImages = images.filter((img) => img.getAttribute('alt') && img.getAttribute('src'))
    // At least some integration cards should have img with src
    expect(integrationImages.length).toBeGreaterThan(0)
    integrationImages.forEach((img) => {
      expect(img).toHaveAttribute('src')
      expect(img).toHaveAttribute('alt')
    })
  })
})
