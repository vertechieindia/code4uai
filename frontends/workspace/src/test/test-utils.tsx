import type React from 'react'
import { render, RenderOptions } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AuthProvider } from '../AuthContext'

export function setAuthStorage(token: string, user: object) {
  const storage = (window as unknown as { __testStorage?: Record<string, string> }).__testStorage
  if (storage) {
    storage['code4u_token'] = token
    storage['code4u_user'] = JSON.stringify(user)
  }
}

export function clearAuthStorage() {
  const storage = (window as unknown as { __testStorage?: Record<string, string> }).__testStorage
  if (storage) {
    delete storage['code4u_token']
    delete storage['code4u_user']
  }
}

interface WrapperOptions {
  initialRoute?: string
  initialEntries?: string[]
}

function createWrapper(options: WrapperOptions = {}) {
  const { initialRoute = '/', initialEntries } = options

  return function Wrapper({ children }: { children: React.ReactNode }) {
    const routerProps = initialEntries
      ? { initialEntries }
      : { initialEntries: [initialRoute] }

    return (
      <MemoryRouter {...routerProps}>
        <AuthProvider>{children}</AuthProvider>
      </MemoryRouter>
    )
  }
}

interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  route?: string
  initialEntries?: string[]
}

export function renderWithProviders(
  ui: React.ReactElement,
  options: CustomRenderOptions = {}
) {
  const { route = '/', initialEntries, ...renderOptions } = options
  const Wrapper = createWrapper({
    initialRoute: route,
    initialEntries,
  })
  return render(ui, {
    wrapper: Wrapper,
    ...renderOptions,
  })
}

export * from '@testing-library/react'
export { default as userEvent } from '@testing-library/user-event'
