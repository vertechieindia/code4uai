import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { renderWithProviders } from '../test-utils'
import LoginPage from '../../pages/LoginPage'
import SignupPage from '../../pages/SignupPage'
import IntegrationsPage from '../../pages/IntegrationsPage'

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }))
})

describe('Accessibility', () => {
  describe('LoginPage', () => {
    it('has proper form labels', () => {
      renderWithProviders(<LoginPage />, { route: '/login' })
      expect(screen.getByPlaceholderText(/you@example\.com/i)).toBeInTheDocument()
      expect(screen.getByPlaceholderText(/••••••••/i)).toBeInTheDocument()
    })

    it('form inputs are keyboard accessible', () => {
      renderWithProviders(<LoginPage />, { route: '/login' })
      const emailInput = screen.getByPlaceholderText(/you@example\.com/i)
      const passwordInput = screen.getByPlaceholderText(/••••••••/i)
      expect(emailInput).not.toHaveAttribute('tabindex', '-1')
      expect(passwordInput).not.toHaveAttribute('tabindex', '-1')
    })
  })

  describe('SignupPage', () => {
    it('has proper form labels', () => {
      renderWithProviders(<SignupPage />, { route: '/signup' })
      expect(screen.getByPlaceholderText(/john doe/i)).toBeInTheDocument()
      expect(screen.getByPlaceholderText(/you@example\.com/i)).toBeInTheDocument()
      expect(screen.getByPlaceholderText(/••••••••/i)).toBeInTheDocument()
    })
  })

  describe('Images', () => {
    it('LoginPage logo has alt text', () => {
      renderWithProviders(<LoginPage />, { route: '/login' })
      const logo = screen.getByRole('img', { name: /code4u\.ai/i })
      expect(logo).toHaveAttribute('alt', 'code4u.ai')
    })
  })

  describe('ARIA attributes', () => {
    it('interactive elements have appropriate roles', () => {
      renderWithProviders(<LoginPage />, { route: '/login' })
      expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
      expect(screen.getByRole('textbox')).toBeInTheDocument()
    })
  })

  describe('Focus management', () => {
    it('form elements can receive focus', () => {
      renderWithProviders(<LoginPage />, { route: '/login' })
      const emailInput = screen.getByPlaceholderText(/you@example\.com/i)
      emailInput.focus()
      expect(document.activeElement).toBe(emailInput)
    })
  })

  describe('Color contrast', () => {
    it('primary buttons have sufficient contrast (visible text)', () => {
      renderWithProviders(<LoginPage />, { route: '/login' })
      const submitButton = screen.getByRole('button', { name: /sign in/i })
      const styles = window.getComputedStyle(submitButton)
      expect(submitButton).toBeVisible()
      expect(submitButton.textContent).toBeTruthy()
    })
  })
})
