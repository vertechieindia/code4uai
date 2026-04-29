# Frontend Test Suite

This directory contains a comprehensive test suite for the code4u.ai React application.

## Running Tests

```bash
# Run all tests
npm run test

# Run tests once (CI mode)
npm run test:run

# Run with coverage
npm run test:coverage
```

## Test Structure

- **`src/test/unit/`** - Unit tests for AuthContext and components
- **`src/test/integration/`** - Integration tests for pages and routing
- **`src/test/accessibility/`** - Accessibility (a11y) tests
- **`src/test/smoke/`** - Smoke tests for app mount and critical paths
- **`src/test/regression/`** - Regression tests for known issues

## React Version Conflict (Monorepo)

If you see "A React Element from an older version of React was rendered", the monorepo may have multiple React copies. Add this to the **root** `package.json`:

```json
"pnpm": {
  "overrides": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  }
}
```

Then run `pnpm install --no-frozen-lockfile` from the repo root.

## Test Utilities

- **`renderWithProviders`** - Renders components with MemoryRouter + AuthProvider
- **`setAuthStorage`** - Sets authenticated state for tests
- **`clearAuthStorage`** - Clears auth state
