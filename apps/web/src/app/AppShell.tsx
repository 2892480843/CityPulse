import { type ReactNode } from 'react'

import { useAuth } from './AuthContext'
import { useRouter } from './RouteContext'
import type { RoleName } from '../shared/api/types'

type NavItem = {
  path: string
  label: string
  hint?: string
  roles?: RoleName[]
}

const NAV_ITEMS: NavItem[] = [
  { path: '/overview', label: '总览' },
  { path: '/data', label: '数据中心', roles: ['admin', 'analyst'] },
  { path: '/predictions', label: '预测' },
  { path: '/actions', label: '经营动作' },
  { path: '/backtests', label: '历史回测', roles: ['admin', 'analyst'] },
  { path: '/system', label: '系统状态' },
  { path: '/admin', label: '系统管理', roles: ['admin'] },
]

const ROLE_LABELS: Record<RoleName, string> = {
  admin: '管理员',
  analyst: '分析师',
  operator: '运营',
}

export function AppShell({ children }: { children: ReactNode }) {
  const { user, logout, hasRole } = useAuth()
  const { path, navigate } = useRouter()
  const items = NAV_ITEMS.filter((item) => item.roles === undefined || hasRole(...item.roles))

  return (
    <div className="shell">
      <aside className="shell-side">
        <div className="brand">
          City<span>Pulse</span>
        </div>
        <p className="brand-sub">热城先知 · 生产平台</p>
        <nav aria-label="主导航" className="shell-nav">
          {items.map((item) => (
            <button
              key={item.path}
              type="button"
              className={path === item.path ? 'nav-link on' : 'nav-link'}
              aria-current={path === item.path ? 'page' : undefined}
              onClick={() => navigate(item.path)}
            >
              <span>{item.label}</span>
              {item.hint ? <small>{item.hint}</small> : null}
            </button>
          ))}
        </nav>
        <div className="shell-user">
          <p className="shell-user-name">{user?.display_name}</p>
          <p className="shell-user-roles">
            {user?.roles.map((role) => ROLE_LABELS[role]).join(' / ')}
          </p>
          <button type="button" className="btn ghost" onClick={() => void logout()}>
            退出登录
          </button>
        </div>
      </aside>
      <main className="shell-main">{children}</main>
    </div>
  )
}
