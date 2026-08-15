import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { useAuth } from '../../app/AuthContext'
import { ApiError } from '../../shared/api/client'
import type { RoleName, UserAdminView } from '../../shared/api/types'
import { createUser, listUsers, updateUser } from './api'

const ROLE_LABELS: Record<RoleName, string> = {
  admin: '管理员',
  analyst: '分析师',
  operator: '运营',
}

const ALL_ROLES: RoleName[] = ['admin', 'analyst', 'operator']

function CreateUserForm() {
  const queryClient = useQueryClient()
  const [username, setUsername] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [roles, setRoles] = useState<RoleName[]>(['analyst'])
  const [error, setError] = useState<string | null>(null)

  const create = useMutation({
    mutationFn: () =>
      createUser({
        username,
        password,
        display_name: displayName,
        roles: roles.length > 0 ? roles : ['analyst'],
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
      setUsername('')
      setDisplayName('')
      setPassword('')
      setRoles(['analyst'])
      setError(null)
    },
    onError: (cause) =>
      setError(cause instanceof ApiError ? `${cause.message}` : '创建失败，请重试。'),
  })

  const toggleRole = (role: RoleName, checked: boolean) => {
    setRoles((current) =>
      checked ? [...new Set([...current, role])] : current.filter((item) => item !== role),
    )
  }

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    create.mutate()
  }

  return (
    <form className="user-form" onSubmit={onSubmit} aria-label="创建用户">
      <h3>创建用户</h3>
      <div className="form-grid">
        <label>
          用户名
          <input
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            pattern="[a-z0-9][a-z0-9_-]*"
            title="小写字母、数字、连字符，字母或数字开头"
            required
          />
        </label>
        <label>
          显示名
          <input
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            required
          />
        </label>
        <label>
          初始密码
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="new-password"
            required
          />
        </label>
        <fieldset className="role-picker">
          <legend>角色</legend>
          {ALL_ROLES.map((role) => (
            <label key={role} className="checkbox">
              <input
                type="checkbox"
                checked={roles.includes(role)}
                onChange={(event) => toggleRole(role, event.target.checked)}
              />
              {ROLE_LABELS[role]}
            </label>
          ))}
        </fieldset>
      </div>
      {error ? (
        <p role="alert" className="form-error">
          {error}
        </p>
      ) : null}
      <button type="submit" className="btn primary" disabled={create.isPending}>
        {create.isPending ? '创建中…' : '创建用户'}
      </button>
      <p className="muted">密码策略：至少 10 位，同时包含字母与数字，且不含用户名。</p>
    </form>
  )
}

function UserRow({ user, selfId }: { user: UserAdminView; selfId: string }) {
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const toggle = useMutation({
    mutationFn: () => updateUser(user.id, { is_active: !user.is_active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin', 'users'] }),
    onError: (cause) =>
      setError(cause instanceof ApiError ? cause.message : '操作失败，请重试。'),
  })
  const isSelf = user.id === selfId

  return (
    <tr>
      <td>
        <strong>{user.display_name}</strong>
        <div className="muted mono">{user.username}</div>
      </td>
      <td>
        {user.roles.map((role) => (
          <span key={role} className={`badge role-${role}`}>
            {ROLE_LABELS[role]}
          </span>
        ))}
      </td>
      <td>
        <span className={`badge ${user.is_active ? 'status-valid' : 'status-invalid'}`}>
          {user.is_active ? '启用' : '禁用'}
        </span>
      </td>
      <td>
        {user.last_login_at ? new Date(user.last_login_at).toLocaleString('zh-CN') : '从未登录'}
      </td>
      <td className="actions">
        <button
          type="button"
          className="btn small"
          disabled={toggle.isPending || isSelf}
          title={isSelf ? '不能禁用自己的账号' : undefined}
          onClick={() => toggle.mutate()}
        >
          {user.is_active ? '禁用' : '启用'}
        </button>
        {error ? (
          <p role="alert" className="form-error">
            {error}
          </p>
        ) : null}
      </td>
    </tr>
  )
}

export function AdminUsersPage() {
  const { user } = useAuth()
  const users = useQuery({ queryKey: ['admin', 'users'], queryFn: listUsers })

  return (
    <section className="page">
      <header>
        <p className="eyebrow">CITYPULSE / ADMIN</p>
        <h1>系统管理 · 用户与角色</h1>
        <p className="muted">
          角色决定页面与接口权限；禁用用户会立即撤销其全部会话，关键操作写入审计日志。
        </p>
      </header>

      {users.isPending ? <p className="muted">正在加载用户…</p> : null}
      {users.isError ? <p role="alert">用户列表加载失败，请稍后重试。</p> : null}
      {users.data ? (
        <>
          <CreateUserForm />
          <table>
            <thead>
              <tr>
                <th>用户</th>
                <th>角色</th>
                <th>状态</th>
                <th>最近登录</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {users.data.items.map((item) => (
                <UserRow key={item.id} user={item} selfId={user?.id ?? ''} />
              ))}
            </tbody>
          </table>
        </>
      ) : null}
    </section>
  )
}
