import { useEffect, type ReactNode } from 'react'

import { AppShell } from './AppShell'
import { AuthProvider, useAuth } from './AuthContext'
import { RouterProvider, useRouter } from './RouteContext'
import { LoginPage } from '../features/auth/LoginPage'
import { DemoPage } from '../features/demo/DemoPage'
import { OverviewPage } from '../features/overview/OverviewPage'
import { DataCenterPage } from '../features/data/DataCenterPage'
import { AdminUsersPage } from '../features/admin/AdminUsersPage'
import { PredictionsPage } from '../features/predictions/PredictionsPage'
import { ActionsPage } from '../features/actions/ActionsPage'
import { BacktestsPage } from '../features/backtests/BacktestsPage'
import { SystemStatusPage } from '../features/system/SystemStatusPage'
import type { RoleName } from '../shared/api/types'

type RouteDefinition = {
  path: string
  element: ReactNode
  roles?: RoleName[]
}

const ROUTES: RouteDefinition[] = [
  { path: '/overview', element: <OverviewPage /> },
  { path: '/data', element: <DataCenterPage />, roles: ['admin', 'analyst'] },
  { path: '/predictions', element: <PredictionsPage /> },
  { path: '/actions', element: <ActionsPage /> },
  { path: '/backtests', element: <BacktestsPage />, roles: ['admin', 'analyst'] },
  { path: '/system', element: <SystemStatusPage /> },
  { path: '/admin', element: <AdminUsersPage />, roles: ['admin'] },
]

function AccessDenied({ path }: { path: string }) {
  return (
    <section className="page">
      <p className="eyebrow">CITYPULSE / 403</p>
      <h1>权限不足</h1>
      <p className="muted">
        当前角色无权访问 {path}。如需相应能力，请联系管理员调整角色分配。
      </p>
    </section>
  )
}

function Routes() {
  const { path, navigate } = useRouter()
  const { status, user, hasRole } = useAuth()

  useEffect(() => {
    if (status === 'anonymous' && path !== '/login' && path !== '/demo') {
      navigate('/login')
    }
    if (status === 'authenticated' && (path === '/login' || path === '/' || path === '')) {
      navigate('/overview')
    }
  }, [status, path, navigate])

  if (status === 'loading') {
    return (
      <main className="center">
        <p>正在恢复会话…</p>
      </main>
    )
  }

  if (status === 'anonymous') {
    return path === '/demo' ? <DemoPage /> : <LoginPage />
  }

  const route = ROUTES.find((candidate) => candidate.path === path)
  const content =
    route === undefined ? (
      <section className="page">
        <p className="eyebrow">CITYPULSE / 404</p>
        <h1>页面不存在</h1>
        <p className="muted">{path} 不在当前系统的页面清单中。</p>
      </section>
    ) : route.roles !== undefined && !hasRole(...route.roles) ? (
      <AccessDenied path={route.path} />
    ) : (
      route.element
    )

  return <AppShell key={user?.id}>{content}</AppShell>
}

export function App() {
  return (
    <RouterProvider>
      <AuthProvider>
        <Routes />
      </AuthProvider>
    </RouterProvider>
  )
}
