import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { LoginPage } from './LoginPage'
import { ApiError } from '../../shared/api/client'

const mocks = vi.hoisted(() => ({
  login: vi.fn(),
}))

vi.mock('../../app/AuthContext', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../app/AuthContext')>()
  return {
    ...actual,
    useAuth: () => ({
      login: mocks.login,
      logout: vi.fn(),
      user: null,
      status: 'anonymous' as const,
      hasRole: () => false,
    }),
  }
})

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <LoginPage />
    </QueryClientProvider>,
  )
}

test('renders the sign-in form with role hint', () => {
  renderPage()

  expect(screen.getByLabelText('用户名')).toBeInTheDocument()
  expect(screen.getByLabelText('密码')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '登录' })).toBeInTheDocument()
})

test('submits credentials to the auth context', async () => {
  mocks.login.mockResolvedValue({
    id: 'u1',
    username: 'analyst',
    display_name: '分析师',
    is_active: true,
    roles: ['analyst'],
  })
  renderPage()

  fireEvent.change(screen.getByLabelText('用户名'), { target: { value: 'analyst' } })
  fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'secret-pass-1' } })
  fireEvent.click(screen.getByRole('button', { name: '登录' }))

  await waitFor(() =>
    expect(mocks.login).toHaveBeenCalledWith({
      username: 'analyst',
      password: 'secret-pass-1',
    }),
  )
})

test('maps INVALID_CREDENTIALS to a friendly message', async () => {
  mocks.login.mockReset()
  mocks.login.mockRejectedValue(
    new ApiError(401, 'INVALID_CREDENTIALS', 'Incorrect username or password.'),
  )
  renderPage()

  fireEvent.change(screen.getByLabelText('用户名'), { target: { value: 'analyst' } })
  fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'wrong-pass-1' } })
  fireEvent.click(screen.getByRole('button', { name: '登录' }))

  expect(await screen.findByText('用户名或密码不正确。')).toBeInTheDocument()
})

test('clicking a demo account fills the form', async () => {
  mocks.login.mockReset()
  mocks.login.mockResolvedValue({
    id: 'u1',
    username: 'analyst',
    display_name: '分析师',
    is_active: true,
    roles: ['analyst'],
  })
  renderPage()

  const analystCard = await screen.findByText('analyst / signal-keeper-88')
  fireEvent.click(analystCard.closest('button') as HTMLButtonElement)

  expect(screen.getByLabelText('用户名')).toHaveValue('analyst')
  expect(screen.getByLabelText('密码')).toHaveValue('signal-keeper-88')
})
