import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { AdminUsersPage } from './AdminUsersPage'
import * as adminApi from './api'
import type { UserListResponse } from '../../shared/api/types'

vi.mock('../../app/AuthContext', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../app/AuthContext')>()
  return {
    ...actual,
    useAuth: () => ({
      login: vi.fn(),
      logout: vi.fn(),
      user: {
        id: 'u-admin',
        username: 'admin',
        display_name: '管理员',
        is_active: true,
        roles: ['admin'],
      },
      status: 'authenticated' as const,
      hasRole: (role: string) => role === 'admin',
    }),
  }
})

vi.mock('./api')

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <AdminUsersPage />
    </QueryClientProvider>,
  )
}

const USERS: UserListResponse = {
  items: [
    {
      id: 'u-admin',
      username: 'admin',
      display_name: '管理员',
      is_active: true,
      roles: ['admin'],
      created_at: '2026-08-15T09:00:00+08:00',
      last_login_at: '2026-08-16T01:00:00+08:00',
    },
    {
      id: 'u-2',
      username: 'analyst',
      display_name: '分析师',
      is_active: true,
      roles: ['analyst'],
      created_at: '2026-08-15T09:00:00+08:00',
      last_login_at: null,
    },
  ],
  total: 2,
}

test('lists users with roles and disables self-toggle', async () => {
  vi.mocked(adminApi.listUsers).mockResolvedValue(USERS)

  renderPage()

  expect(await screen.findByText('管理员', { selector: 'strong' })).toBeInTheDocument()
  expect(screen.getByText('从未登录')).toBeInTheDocument()

  const buttons = screen.getAllByRole('button', { name: '禁用' })
  expect(buttons).toHaveLength(2)
  expect(buttons[0]).toBeDisabled()
  expect(buttons[1]).toBeEnabled()
})

test('creates a user through the form', async () => {
  vi.mocked(adminApi.listUsers).mockResolvedValue(USERS)
  vi.mocked(adminApi.createUser).mockResolvedValue({
    id: 'u-3',
    username: 'shenjunhao',
    display_name: '沈均皓',
    is_active: true,
    roles: ['analyst'],
    created_at: '2026-08-16T01:30:00+08:00',
    last_login_at: null,
  })

  renderPage()

  fireEvent.change(await screen.findByLabelText('用户名'), { target: { value: 'shenjunhao' } })
  fireEvent.change(screen.getByLabelText('显示名'), { target: { value: '沈均皓' } })
  fireEvent.change(screen.getByLabelText('初始密码'), { target: { value: 'dragon-lake-77' } })
  fireEvent.click(screen.getByRole('button', { name: '创建用户' }))

  await waitFor(() =>
    expect(adminApi.createUser).toHaveBeenCalledWith({
      username: 'shenjunhao',
      password: 'dragon-lake-77',
      display_name: '沈均皓',
      roles: ['analyst'],
    }),
  )
})

test('toggling a user calls updateUser', async () => {
  vi.mocked(adminApi.listUsers).mockResolvedValue(USERS)
  vi.mocked(adminApi.updateUser).mockResolvedValue({
    ...USERS.items[1],
    is_active: false,
  })

  renderPage()

  const disableButton = (await screen.findAllByRole('button', { name: '禁用' }))[1]
  fireEvent.click(disableButton)

  await waitFor(() => expect(adminApi.updateUser).toHaveBeenCalledWith('u-2', { is_active: false }))
})
