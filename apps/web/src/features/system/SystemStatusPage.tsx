import { useQuery } from '@tanstack/react-query'

import { getLiveness, getReadiness } from './api'


export function SystemStatusPage() {
  const live = useQuery({ queryKey: ['system', 'live'], queryFn: getLiveness })
  const ready = useQuery({ queryKey: ['system', 'ready'], queryFn: getReadiness })

  if (live.isPending || ready.isPending) {
    return <main aria-busy="true">正在检查 CityPulse 服务…</main>
  }

  if (live.isError || ready.isError) {
    return (
      <main>
        <h1>CityPulse 工程基础</h1>
        <p role="alert">健康检查失败，请核对 API、PostgreSQL 和 Redis 运行状态。</p>
      </main>
    )
  }

  const checks = ready.data.checks
  return (
    <main>
      <header>
        <p className="eyebrow">CITYPULSE / SYSTEM STATUS</p>
        <h1>工程基础已连接</h1>
        <p>版本 {live.data.version}</p>
      </header>
      <section aria-label="服务健康状态" className="status-grid">
        <article>
          <h2>API 进程正常</h2>
          <p>存活检查不依赖外部服务。</p>
        </article>
        <article>
          <h2>PostgreSQL {checks.database.status === 'ok' ? '正常' : '异常'}</h2>
          <p>响应 {checks.database.latency_ms.toFixed(1)} ms</p>
        </article>
        <article>
          <h2>Redis {checks.redis.status === 'ok' ? '正常' : '异常'}</h2>
          <p>响应 {checks.redis.latency_ms.toFixed(1)} ms</p>
        </article>
      </section>
    </main>
  )
}
