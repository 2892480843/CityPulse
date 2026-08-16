import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { useAuth } from '../../app/AuthContext'
import { ApiError } from '../../shared/api/client'
import type { PredictionResult } from '../../shared/api/types'
import { cityEvidence, cityTrend, createRun, listJobs, listRuns, runResults } from './api'
import { downloadCsv } from '../../shared/exportCsv'

const PRIORITY_LABELS: Record<string, string> = {
  high: '行动',
  medium: '验证',
  watch: '观察',
  blocked: '阻断',
}

const FACTOR_LABELS: Record<string, string> = {
  content_growth: '内容增速',
  search_growth: '搜索增速',
  event_trigger: '事件触发',
  accessibility: '可达性',
  supply_capacity: '供给承载',
  weather_fit: '天气适配',
  novelty: '新奇度',
  cross_region_spread: '跨域扩散',
  risk_pressure: '风险压力',
}

function ScoreBar({ value }: { value: number }) {
  return (
    <div className="scorebar" role="img" aria-label={`趋势分 ${value}`}>
      <span style={{ width: `${Math.max(2, Math.min(100, value))}%` }} />
    </div>
  )
}

function CityDetail({ result, runId }: { result: PredictionResult; runId: string }) {
  const trend = useQuery({
    queryKey: ['cityTrend', result.city_code, runId],
    queryFn: () => cityTrend(result.city_code, runId),
  })
  const evidence = useQuery({
    queryKey: ['cityEvidence', result.city_code],
    queryFn: () => cityEvidence(result.city_code),
  })

  return (
    <div className="city-detail">
      <h3>
        {result.city_name}
        <span className="muted"> · {result.province} · {result.city_code}</span>
      </h3>
      <div className="metric-row">
        <div>
          <strong>{result.trend_score}</strong>
          <small>趋势分（非概率）</small>
        </div>
        <div>
          <strong>{result.risk_pressure}</strong>
          <small>风险压力</small>
        </div>
        <div>
          <strong>{Math.round(result.evidence_coverage * 100)}%</strong>
          <small>证据完整度</small>
        </div>
        <div>
          <strong>{PRIORITY_LABELS[result.action_priority]}</strong>
          <small>行动优先级</small>
        </div>
        <div>
          <strong>{result.momentum === null ? '—' : `${result.momentum}×`}</strong>
          <small>窗口动量（近 3 日 / 基线）{result.accelerating ? ' · 异常加速' : ''}</small>
        </div>
      </div>
      {result.blockers.length > 0 ? (
        <p className="notice">
          降级原因：{result.blockers.join('；')}
          {result.data_stale ? '；数据超过 14 天未更新' : ''}
        </p>
      ) : null}
      <h4>因子构成（版本化权重）</h4>
      <div className="factor-list">
        {Object.entries(result.factors).map(([name, value]) => (
          <div className="factor-row" key={name}>
            <span>{FACTOR_LABELS[name] ?? name}</span>
            <ScoreBar value={value} />
            <b>{value}</b>
          </div>
        ))}
      </div>
      {evidence.data ? (
        <>
          <h4>证据链汇总</h4>
          <div className="metric-row">
            <div>
              <strong>{evidence.data.total_observations}</strong>
              <small>观测行数</small>
            </div>
            <div>
              <strong>{Math.round(evidence.data.sourced_share * 100)}%</strong>
              <small>带来源占比</small>
            </div>
            <div>
              <strong>{Math.round(evidence.data.metric_coverage * 100)}%</strong>
              <small>指标覆盖</small>
            </div>
            <div>
              <strong>{evidence.data.sources.length}</strong>
              <small>来源域名数</small>
            </div>
          </div>
          {evidence.data.missing_metrics.length > 0 ? (
            <p className="notice">缺失指标：{evidence.data.missing_metrics.join('、')}</p>
          ) : null}
          <p className="muted">
            覆盖 {evidence.data.date_min} ~ {evidence.data.date_max}；最近可用时间{' '}
            {evidence.data.latest_available_at?.slice(0, 10)}；来源：
            {evidence.data.sources.join('、') || '无'}
          </p>
        </>
      ) : null}
      {trend.data ? (
        <>
          <h4>信号时间序列（近 {trend.data.series_window_days} 天）</h4>
          <table className="series-table">
            <thead>
              <tr>
                <th>指标</th>
                <th>走势（最早 → 最新）</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(trend.data.series).map(([metric, points]) => (
                <tr key={metric}>
                  <td>{FACTOR_LABELS[metric] ?? metric}</td>
                  <td className="mono">
                    {points.map((point) => point.value.toFixed(1)).join(' → ')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : null}
    </div>
  )
}

export function PredictionsPage() {
  const { hasRole } = useAuth()
  const queryClient = useQueryClient()
  const [selectedRun, setSelectedRun] = useState<string | null>(null)
  const [windowDays, setWindowDays] = useState<7 | 14 | 30>(14)
  const [tab, setTab] = useState<'board' | 'jobs'>('board')
  const [error, setError] = useState<string | null>(null)

  const runs = useQuery({ queryKey: ['predictionRuns'], queryFn: listRuns })
  const activeRun = selectedRun ?? runs.data?.items[0]?.id ?? null
  const results = useQuery({
    queryKey: ['predictionResults', activeRun],
    queryFn: () => runResults(activeRun as string),
    enabled: activeRun !== null,
  })
  const jobs = useQuery({
    queryKey: ['jobs'],
    queryFn: listJobs,
    enabled: tab === 'jobs',
    refetchInterval: 5000,
  })

  const create = useMutation({
    mutationFn: () => createRun(windowDays),
    onSuccess: (run) => {
      queryClient.invalidateQueries({ queryKey: ['predictionRuns'] })
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      setSelectedRun(run.id)
      setError(null)
    },
    onError: (cause) =>
      setError(cause instanceof ApiError ? cause.message : '创建失败，请稍后重试。'),
  })

  const [selectedCity, setSelectedCity] = useState<string | null>(null)
  const detail = results.data?.items.find((item) => item.city_code === selectedCity) ?? null

  return (
    <section className="page">
      <header>
        <p className="eyebrow">CITYPULSE / PREDICTIONS</p>
        <h1>预测榜单</h1>
        <p className="muted">
          趋势分是排序分而非概率；行动优先级由证据完整度、风险压力与数据新鲜度共同约束。
        </p>
      </header>

      <div className="tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'board'}
          className={tab === 'board' ? 'tab on' : 'tab'}
          onClick={() => setTab('board')}
        >
          榜单
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'jobs'}
          className={tab === 'jobs' ? 'tab on' : 'tab'}
          onClick={() => setTab('jobs')}
        >
          任务中心
        </button>
      </div>

      {tab === 'board' ? (
        <>
          {hasRole('analyst') ? (
            <div className="toolbar">
              <label className="inline-label">
                预测窗口
                <select
                  aria-label="预测窗口"
                  value={windowDays}
                  onChange={(event) => setWindowDays(Number(event.target.value) as 7 | 14 | 30)}
                >
                  <option value={7}>7 天</option>
                  <option value={14}>14 天</option>
                  <option value={30}>30 天</option>
                </select>
              </label>
              <button
                type="button"
                className="btn primary"
                disabled={create.isPending}
                onClick={() => create.mutate()}
              >
                {create.isPending ? '计算中…' : '创建预测运行'}
              </button>
              {error ? (
                <p role="alert" className="form-error">
                  {error}
                </p>
              ) : null}
            </div>
          ) : null}

          {results.data ? (
            <div className="toolbar">
              <button
                type="button"
                className="btn"
                onClick={() =>
                  downloadCsv(
                    `citypulse-leaderboard-${results.data.run.as_of_date}.csv`,
                    ['排名', '城市', '省份', '趋势分', '风险压力', '证据完整度', '行动优先级', '窗口动量', '异常加速', '数据过期'],
                    results.data.items.map((item) => [
                      item.trend_rank,
                      item.city_name,
                      item.province,
                      item.trend_score,
                      item.risk_pressure,
                      item.evidence_coverage,
                      item.action_priority,
                      item.momentum ?? '',
                      item.accelerating ? '是' : '否',
                      item.data_stale ? '是' : '否',
                    ]),
                    {
                      运行窗口: `${results.data.run.window_days} 天`,
                      数据日期: results.data.run.as_of_date,
                      生成时间: new Date().toISOString(),
                    },
                  )
                }
              >
                导出榜单 CSV
              </button>
            </div>
          ) : null}

          {runs.data && runs.data.items.length > 0 ? (
            <div className="run-select">
              {runs.data.items.map((run) => (
                <button
                  type="button"
                  key={run.id}
                  className={run.id === activeRun ? 'chip on' : 'chip'}
                  onClick={() => setSelectedRun(run.id)}
                >
                  {run.window_days} 天窗 · {run.city_count} 城 ·{' '}
                  {new Date(run.created_at).toLocaleDateString('zh-CN')}
                </button>
              ))}
            </div>
          ) : (
            <p className="muted">还没有预测运行。分析师提交数据集后即可创建。</p>
          )}

          {results.data ? (
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>城市</th>
                  <th>趋势分</th>
                  <th>风险</th>
                  <th>证据</th>
                  <th>优先级</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {results.data.items.map((item) => (
                  <tr
                    key={item.id}
                    className={item.city_code === selectedCity ? 'row-on' : undefined}
                  >
                    <td>{item.trend_rank}</td>
                    <td>
                      <strong>{item.city_name}</strong>
                      <div className="muted">{item.province}</div>
                    </td>
                    <td className="scorecell">
                      <ScoreBar value={item.trend_score} />
                      <b>{item.trend_score}</b>
                    </td>
                    <td>{item.risk_pressure}</td>
                    <td>{Math.round(item.evidence_coverage * 100)}%</td>
                    <td>
                      <span className={`badge priority-${item.action_priority}`}>
                        {PRIORITY_LABELS[item.action_priority]}
                      </span>
                      {item.accelerating ? (
                        <span className="badge accel">异常加速</span>
                      ) : null}
                      {item.data_stale ? <small className="muted"> 数据过期</small> : null}
                    </td>
                    <td>
                      <button
                        type="button"
                        className="btn small"
                        onClick={() => setSelectedCity(item.city_code)}
                      >
                        详情
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}

          {detail && activeRun ? (
            <CityDetail result={detail} runId={activeRun} />
          ) : null}
        </>
      ) : (
        <table>
          <thead>
            <tr>
              <th>类型</th>
              <th>状态</th>
              <th>摘要</th>
              <th>创建时间</th>
            </tr>
          </thead>
          <tbody>
            {(jobs.data?.items ?? []).map((job) => (
              <tr key={job.id}>
                <td className="mono">{job.job_type}</td>
                <td>
                  <span className={`badge job-${job.status}`}>{job.status}</span>
                </td>
                <td>
                  {job.summary ?? '—'}
                  {job.error ? <div className="form-error">{job.error}</div> : null}
                </td>
                <td>{new Date(job.created_at).toLocaleString('zh-CN')}</td>
              </tr>
            ))}
            {jobs.data && jobs.data.items.length === 0 ? (
              <tr>
                <td colSpan={4} className="muted">
                  暂无任务记录。
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      )}
    </section>
  )
}
