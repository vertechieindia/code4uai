import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import { renderWithProviders, setAuthStorage } from '../test-utils'
import CommandPalette from '../../components/CommandPalette'
import IntegrationsPage from '../../pages/IntegrationsPage'
import SecurityPage from '../../pages/SecurityPage'
import AgentPage from '../../pages/AgentPage'

const authUser = { user_id: 'u1', email: 'u@u.com', name: 'User', tenant_id: 't1' }
beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }))
  setAuthStorage('token', authUser)
})

describe('CommandPalette', () => {
  it('renders when opened', async () => {
    const { waitFor } = await import('@testing-library/react')
    renderWithProviders(<CommandPalette />)
    // CommandPalette listens on document - trigger Cmd+K to open it
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true, bubbles: true }))
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/search files, symbols, or navigate/i)).toBeInTheDocument()
    }, { timeout: 2000 })
  })
})

describe('IntegrationsPage', () => {
  it('renders all integration cards', () => {
    renderWithProviders(<IntegrationsPage />)
    // IntegrationsPage has many integration cards - GitHub, GitLab, Slack, etc.
    expect(screen.getByText('Integrations')).toBeInTheDocument()
    expect(screen.getByText('GitHub')).toBeInTheDocument()
    expect(screen.getByText('Slack')).toBeInTheDocument()
    expect(screen.getByText('Jira')).toBeInTheDocument()
    expect(screen.getByText('OpenAI')).toBeInTheDocument()
  })

  it('filters by category', () => {
    renderWithProviders(<IntegrationsPage />)
    // Click on Version Control category filter
    fireEvent.click(screen.getByRole('button', { name: 'Version Control' }))
    // Should show git integrations
    expect(screen.getByText('GitHub')).toBeInTheDocument()
    expect(screen.getByText('GitLab')).toBeInTheDocument()
    expect(screen.getByText('Bitbucket')).toBeInTheDocument()
  })

  it('search works', () => {
    renderWithProviders(<IntegrationsPage />)
    const searchInput = screen.getByPlaceholderText(/search integrations/i)
    fireEvent.change(searchInput, { target: { value: 'GitHub' } })
    expect(screen.getByText('GitHub')).toBeInTheDocument()
    fireEvent.change(searchInput, { target: { value: 'nonexistentxyz' } })
    expect(screen.queryByText('GitHub')).not.toBeInTheDocument()
  })
})

describe('SecurityPage', () => {
  it('renders scanning sections', () => {
    const storage = (window as unknown as { __testStorage?: Record<string, string> }).__testStorage
    if (storage) storage['code4u_workspace'] = '/tmp/test-project'
    renderWithProviders(<SecurityPage />)
    expect(screen.getByText(/security & compliance/i)).toBeInTheDocument()
    expect(screen.getByText(/secret.*credential/i)).toBeInTheDocument()
    expect(screen.getByText(/dependency vulnerabilities/i)).toBeInTheDocument()
    expect(screen.getByText(/static security analysis/i)).toBeInTheDocument()
  })
})

describe('AgentPage', () => {
  it('renders emergency stop button', () => {
    renderWithProviders(<AgentPage />, { route: '/agent' })
    expect(screen.getByRole('button', { name: /emergency stop/i })).toBeInTheDocument()
  })
})
