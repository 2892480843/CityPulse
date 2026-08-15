import { useState, type FormEvent } from 'react'

import { useAuth } from '../../app/AuthContext'
import { ApiError } from '../../shared/api/client'

const ERROR_MESSAGES: Record<string, string> = {
  INVALID_CREDENTIALS: '用户名或密码不正确。',
  LOGIN_RATE_LIMITED: '失败次数过多，账号已临时锁定，请稍后再试。',
  SERVICE_MISCONFIGURED: '登录服务暂不可用，请稍后再试。',
}

export function LoginPage() {
  const { login } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login({ username, password })
    } catch (cause) {
      if (cause instanceof ApiError) {
        setError(ERROR_MESSAGES[cause.code] ?? `登录失败：${cause.message}`)
      } else {
        setError('网络异常，请稍后再试。')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="login-wrap">
      <form className="login-card" onSubmit={onSubmit} aria-labelledby="login-title">
        <p className="eyebrow">CITYPULSE 热城先知</p>
        <h1 id="login-title">登录生产平台</h1>
        <p className="muted">
          面向管理员、分析师与运营人员的工作台。首次部署请使用 bootstrap 命令创建的账号。
        </p>
        <label htmlFor="login-username">
          用户名
          <input
            id="login-username"
            name="username"
            autoComplete="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            required
            minLength={3}
          />
        </label>
        <label htmlFor="login-password">
          密码
          <input
            id="login-password"
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>
        {error ? (
          <p role="alert" className="form-error">
            {error}
          </p>
        ) : null}
        <button type="submit" className="btn primary" disabled={submitting}>
          {submitting ? '正在登录…' : '登录'}
        </button>
      </form>
    </main>
  )
}
