import { useQuery } from '@tanstack/react-query'

import { getLiveness, getReadiness } from './api'


export function SystemStatusPage() {
  const live = useQuery({ queryKey: ['system', 'live'], queryFn: getLiveness })
  const ready = useQuery({ queryKey: ['system', 'ready'], queryFn: getReadiness })

  if (live.isPending || ready.isPending) {
    return (
      <section className="page" aria-busy="true">
        <p className="muted">正在检查 CityPulse 服务…</p>
      </section>
    )
  }

  if (live.isError || ready.isError) {
    return (
      <section className="page">
        <p className="eyebrow">CITYPULSE / SYSTEM</p>
        <h1>系统状态</h1>
        <p role="alert">健康检查失败，请核对 API、PostgreSQL 和 Redis 运行状态。</p>
      </section>
    )
  }

  const checks = ready.data.checks
  return (
    <section className="page">
      <header>
        <p className="eyebrow">CITYPULSE / SYSTEM</p>
        <h1>系统状态</h1>
        <p className="muted">版本 {live.data.version}</p>
      </header>
      <div className="status-grid">
        <article>
          <h2>API 进程正常</h2>
          <p className="muted">存活检查不依赖外部服务。</p>
        </article>
        <article>
          <h2>PostgreSQL {checks.database.status === 'ok' ? '正常' : '异常'}</h2>
          <p className="muted">响应 {checks.database.latency_ms.toFixed(1)} ms</p>
        </article>
        <article>
          <h2>Redis {checks.redis.status === 'ok' ? '正常' : '异常'}</h2>
          <p className="muted">响应 {checks.redis.latency_ms.toFixed(1)} ms</p>
        </article>
      </div>
    </section>
  )
}
