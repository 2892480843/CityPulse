import { useQuery } from '@tanstack/react-query'

import { useAuth } from '../../app/AuthContext'
import { useRouter } from '../../app/RouteContext'
import { getLiveness, getReadiness } from '../system/api'
import { listDatasets } from '../data/api'

const STATUS_TEXT = { ok: '正常', error: '异常', degraded: '降级' } as const

export function OverviewPage() {
  const { user } = useAuth()
  const { navigate } = useRouter()
  const live = useQuery({ queryKey: ['system', 'live'], queryFn: getLiveness })
  const ready = useQuery({ queryKey: ['system', 'ready'], queryFn: getReadiness })
  const datasets = useQuery({ queryKey: ['datasets'], queryFn: listDatasets, retry: false })

  const counts =
    datasets.data?.items.reduce<Record<string, number>>((accumulator, dataset) => {
      accumulator[dataset.status] = (accumulator[dataset.status] ?? 0) + 1
      return accumulator
    }, {}) ?? null

  return (
    <section className="page">
      <header>
        <p className="eyebrow">CITYPULSE / OVERVIEW</p>
        <h1>下午好，{user?.display_name}</h1>
        <p className="muted">
          当前为阶段 2（身份与数据）。预测、动作与回测模块将在数据版本积累后上线。
        </p>
      </header>

      <div className="status-grid">
        <article>
          <h2>API 版本</h2>
          <p>{live.isPending ? '检查中…' : live.data ? live.data.version : '暂不可用'}</p>
        </article>
        <article>
          <h2>服务就绪</h2>
          <p>
            {ready.isPending
              ? '检查中…'
              : ready.data
                ? STATUS_TEXT[ready.data.status]
                : '暂不可用'}
          </p>
          {ready.data ? (
            <p className="muted">
              PostgreSQL {STATUS_TEXT[ready.data.checks.database.status]} · Redis{' '}
              {STATUS_TEXT[ready.data.checks.redis.status]}
            </p>
          ) : null}
        </article>
        <article>
          <h2>数据集</h2>
          <p>{counts ? `共 ${datasets.data?.total ?? 0} 个` : '无权限或加载失败'}</p>
          {counts ? (
            <p className="muted">
              {Object.entries(counts)
                .map(([status, count]) => `${status} × ${count}`)
                .join(' · ')}
            </p>
          ) : null}
        </article>
      </div>

      <div className="status-grid">
        <article>
          <h2>下一步</h2>
          <p className="muted">
            在数据中心上传 CSV/XLSX 样例，通过校验后提交不可变数据版本；
            城市目录用于核对 city_code。
          </p>
          <button type="button" className="btn" onClick={() => navigate('/data')}>
            前往数据中心
          </button>
        </article>
        <article>
          <h2>合规提醒</h2>
          <p className="muted">
            演示工作区数据不得进入生产榜单；生产结果必须绑定数据版本、评分版本与代码版本。
          </p>
        </article>
        <article>
          <h2>会话</h2>
          <p className="muted">闲置 30 分钟或累计 12 小时后自动失效；写操作需要 CSRF 令牌。</p>
        </article>
      </div>
    </section>
  )
}
