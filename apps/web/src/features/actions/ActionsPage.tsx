import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { useAuth } from '../../app/AuthContext'
import { ApiError } from '../../shared/api/client'
import type { ActionPlan } from '../../shared/api/types'
import { generatePlan, listPlans, reviewPlan, submitPlan, updatePlan } from './api'
import { downloadCsv } from '../../shared/exportCsv'
import { listRuns, runResults } from '../predictions/api'

const STATUS_LABELS: Record<string, string> = {
  draft: '草稿',
  pending_review: '待审批',
  approved: '已批准',
  rejected: '已驳回',
  archived: '已归档',
}

function PlanDetail({ plan }: { plan: ActionPlan }) {
  const { hasRole } = useAuth()
  const queryClient = useQueryClient()
  const [theme, setTheme] = useState(plan.campaign_theme)
  const [comment, setComment] = useState('')
  const [error, setError] = useState<string | null>(null)

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['actionPlans'] })

  const save = useMutation({
    mutationFn: () => updatePlan(plan.id, { campaign_theme: theme }),
    onSuccess: refresh,
    onError: (cause) => setError(cause instanceof ApiError ? cause.message : '保存失败。'),
  })
  const submit = useMutation({
    mutationFn: () => submitPlan(plan.id),
    onSuccess: refresh,
    onError: (cause) => setError(cause instanceof ApiError ? cause.message : '提交失败。'),
  })
  const review = useMutation({
    mutationFn: (decision: 'approved' | 'rejected') => reviewPlan(plan.id, decision, comment),
    onSuccess: refresh,
    onError: (cause) => setError(cause instanceof ApiError ? cause.message : '审批失败。'),
  })

  const canEdit = hasRole('analyst', 'operator') && plan.status === 'draft'
  const canSubmit = hasRole('analyst', 'operator') && plan.status === 'draft'
  const canReview = hasRole('operator') && plan.status === 'pending_review'

  return (
    <div className="plan-detail">
      <h3>
        {plan.city_name}
        <span className={`badge plan-${plan.status}`}>{STATUS_LABELS[plan.status]}</span>
        <span className="badge role-analyst">
          {plan.generator_type === 'deepseek' ? 'DeepSeek' : '规则模板'}
        </span>
      </h3>
      <p className="muted">{plan.generation_note}</p>

      <dl className="plan-facts">
        <div>
          <dt>目标客群</dt>
          <dd>{plan.target_segment}</dd>
        </div>
        <div>
          <dt>行动窗口</dt>
          <dd>
            {plan.action_window_start} ~ {plan.action_window_end}
          </dd>
        </div>
        <div>
          <dt>产品组合</dt>
          <dd>
            {plan.product_bundle.map((item) => `${item.type}（${item.reason}）`).join('；')}
          </dd>
        </div>
        <div>
          <dt>供给动作</dt>
          <dd>{plan.supply_actions.join('；')}</dd>
        </div>
        <div>
          <dt>假设</dt>
          <dd>{plan.assumptions.join('；')}</dd>
        </div>
        <div>
          <dt>风险与停止条件</dt>
          <dd>{plan.risk_notes}</dd>
        </div>
      </dl>

      {canEdit ? (
        <label className="inline-label">
          投放主题（可编辑）
          <textarea rows={2} value={theme} onChange={(event) => setTheme(event.target.value)} />
        </label>
      ) : (
        <p>
          <strong>投放主题：</strong>
          {plan.campaign_theme}
        </p>
      )}
      {plan.review_comment ? (
        <p className="notice">审批意见：{plan.review_comment}</p>
      ) : null}
      {error ? (
        <p role="alert" className="form-error">
          {error}
        </p>
      ) : null}

      <div className="toolbar">
        {canEdit ? (
          <button
            type="button"
            className="btn"
            disabled={save.isPending}
            onClick={() => save.mutate()}
          >
            保存修改
          </button>
        ) : null}
        {canSubmit ? (
          <button
            type="button"
            className="btn primary"
            disabled={submit.isPending}
            onClick={() => submit.mutate()}
          >
            提交审批
          </button>
        ) : null}
        {canReview ? (
          <>
            <input
              aria-label="审批意见"
              placeholder="审批意见（可留空）"
              value={comment}
              onChange={(event) => setComment(event.target.value)}
            />
            <button
              type="button"
              className="btn primary"
              disabled={review.isPending}
              onClick={() => review.mutate('approved')}
            >
              批准
            </button>
            <button
              type="button"
              className="btn"
              disabled={review.isPending}
              onClick={() => review.mutate('rejected')}
            >
              驳回
            </button>
          </>
        ) : null}
      </div>
    </div>
  )
}

export function ActionsPage() {
  const { hasRole } = useAuth()
  const queryClient = useQueryClient()
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [selected, setSelected] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const plans = useQuery({
    queryKey: ['actionPlans', statusFilter],
    queryFn: () => listPlans(statusFilter || undefined),
  })
  const runs = useQuery({ queryKey: ['predictionRuns'], queryFn: listRuns })
  const latestRun = runs.data?.items[0]?.id ?? null
  const results = useQuery({
    queryKey: ['predictionResults', latestRun],
    queryFn: () => runResults(latestRun as string),
    enabled: latestRun !== null,
  })

  const generate = useMutation({
    mutationFn: (resultId: string) => generatePlan(resultId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['actionPlans'] })
      setError(null)
    },
    onError: (cause) => setError(cause instanceof ApiError ? cause.message : '生成失败。'),
  })

  const plan = plans.data?.items.find((item) => item.id === selected) ?? plans.data?.items[0] ?? null

  return (
    <section className="page">
      <header>
        <p className="eyebrow">CITYPULSE / ACTIONS</p>
        <h1>经营动作</h1>
        <p className="muted">
          动作草案由规则模板或 DeepSeek 生成，事实字段来自预测结果与证据；只有运营人员可以批准或驳回。
        </p>
      </header>

      {hasRole('analyst', 'operator') && results.data ? (
        <div className="toolbar">
          <label className="inline-label">
            从最新运行生成
            <select
              aria-label="选择城市结果"
              onChange={(event) => event.target.value && generate.mutate(event.target.value)}
              defaultValue=""
            >
              <option value="">选择城市…</option>
              {results.data.items.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.trend_rank}. {item.city_name}（趋势 {item.trend_score}）
                </option>
              ))}
            </select>
          </label>
          {error ? (
            <p role="alert" className="form-error">
              {error}
            </p>
          ) : null}
        </div>
      ) : null}

      {plans.data && plans.data.items.length > 0 ? (
        <div className="toolbar">
          <button
            type="button"
            className="btn"
            onClick={() =>
              downloadCsv(
                'citypulse-action-plans.csv',
                ['城市', '状态', '生成方式', '目标客群', '行动窗口', '投放主题', '创建时间'],
                plans.data.items.map((item) => [
                  item.city_name,
                  item.status,
                  item.generator_type,
                  item.target_segment,
                  `${item.action_window_start ?? '—'} ~ ${item.action_window_end ?? '—'}`,
                  item.campaign_theme,
                  item.created_at,
                ]),
                { 状态筛选: statusFilter || '全部', 生成时间: new Date().toISOString() },
              )
            }
          >
            导出动作清单 CSV
          </button>
        </div>
      ) : null}

      <div className="toolbar">
        <select
          aria-label="状态筛选"
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value)}
        >
          <option value="">全部状态</option>
          <option value="draft">草稿</option>
          <option value="pending_review">待审批</option>
          <option value="approved">已批准</option>
          <option value="rejected">已驳回</option>
        </select>
      </div>

      <table>
        <thead>
          <tr>
            <th>城市</th>
            <th>状态</th>
            <th>生成方式</th>
            <th>创建时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {(plans.data?.items ?? []).map((item) => (
            <tr key={item.id} className={plan?.id === item.id ? 'row-on' : undefined}>
              <td>
                <strong>{item.city_name}</strong>
              </td>
              <td>
                <span className={`badge plan-${item.status}`}>{STATUS_LABELS[item.status]}</span>
              </td>
              <td>{item.generator_type === 'deepseek' ? 'DeepSeek' : '规则模板'}</td>
              <td>{new Date(item.created_at).toLocaleString('zh-CN')}</td>
              <td>
                <button
                  type="button"
                  className="btn small"
                  onClick={() => setSelected(item.id)}
                >
                  查看
                </button>
              </td>
            </tr>
          ))}
          {plans.data && plans.data.items.length === 0 ? (
            <tr>
              <td colSpan={5} className="muted">
                暂无动作草案。从最新预测运行选择城市生成第一份草案。
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>

      {plan ? <PlanDetail key={plan.id} plan={plan} /> : null}
    </section>
  )
}
