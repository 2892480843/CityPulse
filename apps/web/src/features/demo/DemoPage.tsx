import { useQuery } from '@tanstack/react-query'
import { useRouter } from '../../app/RouteContext'
import { getJson } from '../../shared/api/client'

type DemoSummary = {
  disclaimer: string
  city_catalog_size: number
  dataset_count: number
  observation_count: number
  sources: { label: string; kind: string; last_synced_at: string | null; last_status: string | null }[]
  latest_run: { window_days: number; as_of_date: string; city_count: number; created_at: string } | null
  leaderboard: {
    rank: number
    city_name: string
    province: string
    trend_score: number
    risk_pressure: number
    evidence_coverage: number
    action_priority: string
    momentum: number | null
    accelerating: boolean
  }[]
  latest_backtest: {
    t0: string
    targets: string[]
    controls: string[]
    hit_at_5: number | null
    hit_at_5_note: string | null
    mean_lead_days: number | null
    false_alerts_per_100: number | null
    evidence_coverage: number | null
    snapshots: { offset_days: number; ranking: { city_code: string; trend_score: number }[] }[]
  } | null
  featured_plans: {
    city_name: string
    status: string
    generator_type: string
    target_segment: string
    campaign_theme: string
    action_window: string
    supply_actions: string[]
    risk_notes: string
  }[]
}

const PRIORITY_LABELS: Record<string, string> = {
  high: '行动',
  medium: '验证',
  watch: '观察',
  blocked: '阻断',
}

const STATUS_LABELS: Record<string, string> = {
  pending_review: '待审批',
  approved: '已批准',
}

const fetchSummary = () => getJson<DemoSummary>('/api/v1/demo/summary')

export function DemoPage() {
  const { navigate } = useRouter()
  const summary = useQuery({ queryKey: ['demoSummary'], queryFn: fetchSummary })

  if (summary.isPending) {
    return (
      <main className="demo-wrap">
        <p className="muted">正在加载演示结果…</p>
      </main>
    )
  }
  if (summary.isError || !summary.data) {
    return (
      <main className="demo-wrap">
        <p role="alert">演示数据加载失败，请确认 API 正在运行。</p>
        <button type="button" className="btn" onClick={() => summary.refetch()}>
          重试
        </button>
      </main>
    )
  }

  const data = summary.data
  const bt = data.latest_backtest

  return (
    <main className="demo-wrap">
      <header className="demo-header">
        <div className="brand-light">
          City<span>Pulse</span> <small>热城先知</small>
        </div>
        <h1>在热度形成前 7-14 天，识别、解释、行动</h1>
        <p className="muted">
          目的地热度预测引擎 · 演示工作区结果总览（只读，无需登录）
        </p>
        <p className="demo-disclaimer" role="note">
          {data.disclaimer}
        </p>
        <button type="button" className="btn primary" onClick={() => navigate('/login')}>
          登录体验完整平台 →
        </button>
      </header>

      <div className="metric-cards">
        <article>
          <h2>{data.city_catalog_size}</h2>
          <p>城市目录（真实行政区划）</p>
        </article>
        <article>
          <h2>{data.observation_count.toLocaleString()}</h2>
          <p>已提交观测行</p>
        </article>
        <article>
          <h2>{data.dataset_count}</h2>
          <p>不可变数据版本</p>
        </article>
        <article>
          <h2>{data.sources.filter((s) => s.last_status === 'succeeded').length}/{data.sources.length}</h2>
          <p>官方开放数据源同步</p>
        </article>
      </div>

      <section className="demo-section">
        <h2>
          预测榜单
          {data.latest_run ? (
            <small className="muted">
              {' '}
              · {data.latest_run.window_days} 天窗口 · 数据日期 {data.latest_run.as_of_date}
            </small>
          ) : null}
        </h2>
        {data.leaderboard.length === 0 ? (
          <p className="muted">暂无已成功的预测运行。</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>城市</th>
                <th>趋势分</th>
                <th>风险</th>
                <th>证据</th>
                <th>优先级</th>
              </tr>
            </thead>
            <tbody>
              {data.leaderboard.map((item) => (
                <tr key={item.rank}>
                  <td>{item.rank}</td>
                  <td>
                    <strong>{item.city_name}</strong>
                    <div className="muted">{item.province}</div>
                  </td>
                  <td>
                    <b>{item.trend_score}</b>
                  </td>
                  <td>{item.risk_pressure}</td>
                  <td>{Math.round(item.evidence_coverage * 100)}%</td>
                  <td>
                    <span className={`badge priority-${item.action_priority}`}>
                      {PRIORITY_LABELS[item.action_priority] ?? item.action_priority}
                    </span>
                    {item.accelerating ? <span className="badge accel">异常加速</span> : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="demo-section">
        <h2>历史回测 · 时间截断验证</h2>
        {bt ? (
          <>
            <div className="metric-row">
              <div>
                <strong>{bt.hit_at_5 === null ? '—' : `${Math.round(bt.hit_at_5 * 100)}%`}</strong>
                <small>Hit@5{bt.hit_at_5_note ? '（描述性）' : ''}</small>
              </div>
              <div>
                <strong>{bt.mean_lead_days === null ? '—' : `${bt.mean_lead_days} 天`}</strong>
                <small>平均提前量</small>
              </div>
              <div>
                <strong>{bt.false_alerts_per_100 ?? '—'}</strong>
                <small>误报 / 100 城市日</small>
              </div>
              <div>
                <strong>
                  {bt.evidence_coverage === null ? '—' : `${Math.round(bt.evidence_coverage * 100)}%`}
                </strong>
                <small>证据覆盖</small>
              </div>
            </div>
            <table>
              <thead>
                <tr>
                  <th>截点</th>
                  <th>排名快照（城市 / 趋势分）</th>
                </tr>
              </thead>
              <tbody>
                {bt.snapshots.map((snapshot) => (
                  <tr key={snapshot.offset_days}>
                    <td>T0-{snapshot.offset_days}</td>
                    <td className="mono">
                      {snapshot.ranking
                        .map((entry) => `${entry.city_code} / ${entry.trend_score}`)
                        .join('，') || '截点前无可获得数据'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        ) : (
          <p className="muted">暂无已成功的回测运行。</p>
        )}
      </section>

      <section className="demo-section">
        <h2>经营动作草案</h2>
        {data.featured_plans.length === 0 ? (
          <p className="muted">暂无待审或已批准的动作方案。</p>
        ) : (
          data.featured_plans.map((plan) => (
            <div className="plan-detail" key={`${plan.city_name}-${plan.campaign_theme}`}>
              <h3>
                {plan.city_name}
                <span className={`badge plan-${plan.status}`}>
                  {STATUS_LABELS[plan.status] ?? plan.status}
                </span>
                <span className="badge role-analyst">
                  {plan.generator_type === 'deepseek' ? 'DeepSeek 生成' : '规则模板'}
                </span>
              </h3>
              <dl className="plan-facts">
                <div>
                  <dt>目标客群</dt>
                  <dd>{plan.target_segment}</dd>
                </div>
                <div>
                  <dt>行动窗口</dt>
                  <dd>{plan.action_window}</dd>
                </div>
                <div>
                  <dt>投放主题</dt>
                  <dd>{plan.campaign_theme}</dd>
                </div>
                <div>
                  <dt>供给动作</dt>
                  <dd>{plan.supply_actions.join('；')}</dd>
                </div>
              </dl>
            </div>
          ))
        )}
      </section>

      <footer className="demo-footer muted">
        数据源：
        {data.sources.map((source) => source.label).join(' · ')}
        <br />
        概率展示门禁按设计规格保持关闭；本页为只读聚合，写操作与审批请登录后进行。
      </footer>
    </main>
  )
}
