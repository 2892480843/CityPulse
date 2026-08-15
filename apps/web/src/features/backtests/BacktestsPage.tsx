import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { useAuth } from '../../app/AuthContext'
import { ApiError } from '../../shared/api/client'
import type { BacktestRun } from '../../shared/api/types'
import { createBacktest, listBacktests, listCities } from './api'

function MetricsCards({ metrics }: { metrics: NonNullable<BacktestRun['metrics']> }) {
  return (
    <div className="metric-cards">
      <article>
        <h2>Hit@5</h2>
        <p>{metrics.hit_at_5 === null ? '—' : `${Math.round(metrics.hit_at_5 * 100)}%`}</p>
        {metrics.hit_at_5_note ? <small className="muted">{metrics.hit_at_5_note}</small> : null}
      </article>
      <article>
        <h2>平均提前量</h2>
        <p>{metrics.mean_lead_days === null ? '—' : `${metrics.mean_lead_days} 天`}</p>
        <small className="muted">首次越阈截点距 T0</small>
      </article>
      <article>
        <h2>误报 / 100 城市日</h2>
        <p>{metrics.false_alerts_per_100 === null ? '—' : metrics.false_alerts_per_100}</p>
        <small className="muted">对照组越阈次数</small>
      </article>
      <article>
        <h2>证据覆盖</h2>
        <p>
          {metrics.evidence_coverage === null
            ? '—'
            : `${Math.round(metrics.evidence_coverage * 100)}%`}
        </p>
        <small className="muted">必需指标在场比例</small>
      </article>
    </div>
  );
}

export function BacktestsPage() {
  const { hasRole } = useAuth()
  const queryClient = useQueryClient()
  const cities = useQuery({ queryKey: ['citiesAll'], queryFn: listCities })
  const runs = useQuery({ queryKey: ['backtests'], queryFn: listBacktests })

  const [t0, setT0] = useState('2026-07-15')
  const [targets, setTargets] = useState<string[]>([])
  const [controls, setControls] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)

  const create = useMutation({
    mutationFn: () =>
      createBacktest({
        t0,
        target_city_codes: targets,
        control_city_codes: controls,
        window_days: 14,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['backtests'] })
      setError(null)
    },
    onError: (cause) => setError(cause instanceof ApiError ? cause.message : '创建失败。'),
  })

  const toggle = (
    list: string[],
    setList: (value: string[]) => void,
    code: string,
  ) => {
    setList(list.includes(code) ? list.filter((item) => item !== code) : [...list, code])
  }

  const [selected, setSelected] = useState<string | null>(null)
  const run = runs.data?.items.find((item) => item.id === selected) ?? runs.data?.items[0] ?? null

  return (
    <section className="page">
      <header>
        <p className="eyebrow">CITYPULSE / BACKTESTS</p>
        <h1>历史回测</h1>
        <p className="muted">
          每个截点只读取 available_at 之前可获得的数据重建排名，杜绝未来信息泄漏；指标绑定当前评分版本。
        </p>
      </header>

      {hasRole('analyst') ? (
        <form
          className="backtest-form"
          onSubmit={(event) => {
            event.preventDefault()
            create.mutate()
          }}
        >
          <label className="inline-label">
            公开爆发日 T0
            <input
              type="date"
              value={t0}
              onChange={(event) => setT0(event.target.value)}
              required
            />
          </label>
          <fieldset className="role-picker wide">
            <legend>正例城市（目标）</legend>
            {(cities.data?.items ?? []).map((city) => (
              <label key={city.id} className="checkbox">
                <input
                  type="checkbox"
                  checked={targets.includes(city.code)}
                  onChange={() => toggle(targets, setTargets, city.code)}
                />
                {city.name}
              </label>
            ))}
          </fieldset>
          <fieldset className="role-picker wide">
            <legend>对照城市</legend>
            {(cities.data?.items ?? []).map((city) => (
              <label key={city.id} className="checkbox">
                <input
                  type="checkbox"
                  checked={controls.includes(city.code)}
                  onChange={() => toggle(controls, setControls, city.code)}
                />
                {city.name}
              </label>
            ))}
          </fieldset>
          <button
            type="submit"
            className="btn primary"
            disabled={create.isPending || targets.length === 0}
          >
            {create.isPending ? '计算中…' : '运行回测（T0-30/14/7 截点）'}
          </button>
          {error ? (
            <p role="alert" className="form-error">
              {error}
            </p>
          ) : null}
        </form>
      ) : null}

      {runs.data && runs.data.items.length > 0 ? (
        <div className="run-select">
          {runs.data.items.map((item) => (
            <button
              type="button"
              key={item.id}
              className={item.id === run?.id ? 'chip on' : 'chip'}
              onClick={() => setSelected(item.id)}
            >
              T0 {item.t0} · 正例 {item.target_city_codes.length}
            </button>
          ))}
        </div>
      ) : (
        <p className="muted">还没有回测运行。</p>
      )}

      {run?.metrics ? (
        <>
          <MetricsCards metrics={run.metrics} />
          <h3>各截点排名快照</h3>
          <table>
            <thead>
              <tr>
                <th>截点</th>
                <th>排名（城市 / 趋势分）</th>
                <th>证据覆盖</th>
              </tr>
            </thead>
            <tbody>
              {run.metrics.snapshots.map((snapshot) => (
                <tr key={snapshot.offset_days}>
                  <td>
                    T0-{snapshot.offset_days}
                    <div className="muted mono">{snapshot.cutoff_at.slice(0, 10)}</div>
                  </td>
                  <td>
                    {snapshot.ranking.length === 0 ? (
                      <span className="muted">截点前无可获得数据</span>
                    ) : (
                      snapshot.ranking
                        .map((entry) => `${entry.city_code} / ${entry.trend_score}`)
                        .join('，')
                    )}
                  </td>
                  <td>{Math.round(snapshot.evidence_coverage * 100)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : null}
    </section>
  )
}
