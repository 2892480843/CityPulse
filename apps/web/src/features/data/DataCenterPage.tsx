import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { useAuth } from '../../app/AuthContext'
import { ApiError } from '../../shared/api/client'
import type { Dataset, ValidationIssue } from '../../shared/api/types'
import {
  commitDataset,
  listDatasets,
  searchCities,
  uploadDataset,
  validateDataset,
} from './api'

const STATUS_LABELS: Record<Dataset['status'], string> = {
  uploaded: '已上传',
  validating: '校验中',
  valid: '校验通过',
  invalid: '校验失败',
  committed: '已提交',
  archived: '已归档',
}

function IssueList({ title, issues, tone }: {
  title: string
  issues: ValidationIssue[]
  tone: 'error' | 'warning'
}) {
  if (issues.length === 0) return null
  return (
    <div className={`report-block ${tone}`}>
      <h4>{title}（{issues.length}）</h4>
      <ul>
        {issues.slice(0, 10).map((issue, index) => (
          <li key={index}>
            <code>{issue.code}</code>
            {issue.row !== null ? ` 第 ${issue.row} 行` : ''}
            {issue.column ? ` 字段 ${issue.column}` : ''}：{issue.message}
          </li>
        ))}
        {issues.length > 10 ? <li>…其余 {issues.length - 10} 条从略</li> : null}
      </ul>
    </div>
  )
}

function DatasetRow({ dataset, canAct }: { dataset: Dataset; canAct: boolean }) {
  const queryClient = useQueryClient()
  const [detail, setDetail] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['datasets'] })
  const validate = useMutation({
    mutationFn: () => validateDataset(dataset.id),
    onSuccess: refresh,
    onError: (error) =>
      setActionError(error instanceof ApiError ? error.message : '操作失败，请重试'),
  })
  const commit = useMutation({
    mutationFn: () => commitDataset(dataset.id),
    onSuccess: refresh,
    onError: (error) =>
      setActionError(error instanceof ApiError ? error.message : '操作失败，请重试'),
  })

  return (
    <>
      <tr>
        <td>
          <strong>{dataset.source_name}</strong>
          <div className="muted">{dataset.original_filename}</div>
        </td>
        <td>
          <span className={`badge status-${dataset.status}`}>
            {STATUS_LABELS[dataset.status]}
          </span>
        </td>
        <td>{dataset.report ? `${dataset.report.row_count} 行 / ${dataset.report.city_count} 城` : '—'}</td>
        <td className="mono">{dataset.sha256.slice(0, 12)}…</td>
        <td>{new Date(dataset.created_at).toLocaleString('zh-CN')}</td>
        <td className="actions">
          <button type="button" className="btn small" onClick={() => setDetail(!detail)}>
            {detail ? '收起' : '详情'}
          </button>
          {canAct && dataset.status === 'uploaded' ? (
            <button
              type="button"
              className="btn small"
              disabled={validate.isPending}
              onClick={() => validate.mutate()}
            >
              {validate.isPending ? '校验中…' : '校验'}
            </button>
          ) : null}
          {canAct && dataset.status === 'valid' ? (
            <button
              type="button"
              className="btn small primary"
              disabled={commit.isPending}
              onClick={() => commit.mutate()}
            >
              {commit.isPending ? '提交中…' : '提交'}
            </button>
          ) : null}
        </td>
      </tr>
      {detail ? (
        <tr className="detail-row">
          <td colSpan={6}>
            <p className="muted">
              来源类型 {dataset.source_type === 'official_sync' ? '官方同步' : '分析师生传'}；
              合法性声明：{dataset.legal_basis}
            </p>
            {dataset.report ? (
              <>
                <p className="muted">
                  覆盖日期 {dataset.report.metric_date_min ?? '—'} 至{' '}
                  {dataset.report.metric_date_max ?? '—'}
                </p>
                <IssueList title="阻断错误" issues={dataset.report.errors} tone="error" />
                <IssueList title="警告" issues={dataset.report.warnings} tone="warning" />
                {dataset.report.errors.length === 0 && dataset.report.warnings.length === 0 ? (
                  <p className="muted">校验无错误与警告。</p>
                ) : null}
              </>
            ) : (
              <p className="muted">尚未运行校验。</p>
            )}
            {actionError ? (
              <p role="alert" className="form-error">
                {actionError}
              </p>
            ) : null}
          </td>
        </tr>
      ) : null}
    </>
  )
}

function CityCatalogPanel() {
  const [query, setQuery] = useState('')
  const cities = useQuery({
    queryKey: ['cities', query],
    queryFn: () => searchCities(query),
  })

  return (
    <section aria-label="城市目录">
      <div className="toolbar">
        <input
          aria-label="搜索城市"
          placeholder="按名称、省份或行政区划代码搜索"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>
      {cities.isPending ? <p className="muted">正在加载城市目录…</p> : null}
      {cities.isError ? <p role="alert">城市目录加载失败，请稍后重试。</p> : null}
      {cities.data ? (
        <table>
          <thead>
            <tr>
              <th>区划代码</th>
              <th>城市</th>
              <th>省份</th>
            </tr>
          </thead>
          <tbody>
            {cities.data.items.map((city) => (
              <tr key={city.id}>
                <td className="mono">{city.code}</td>
                <td>{city.name}</td>
                <td>{city.province}</td>
              </tr>
            ))}
            {cities.data.items.length === 0 ? (
              <tr>
                <td colSpan={3} className="muted">
                  没有匹配的城市。
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      ) : null}
    </section>
  )
}

function UploadPanel({ onNotice }: { onNotice: (message: string) => void }) {
  const queryClient = useQueryClient()
  const [file, setFile] = useState<File | null>(null)
  const [sourceName, setSourceName] = useState('')
  const [legalBasis, setLegalBasis] = useState('')
  const [formError, setFormError] = useState<string | null>(null)

  const upload = useMutation({
    mutationFn: (form: FormData) => uploadDataset(form),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['datasets'] })
      onNotice(
        data.already_exists
          ? `内容未变化：已关联现有数据集 ${data.dataset.source_name}（SHA-256 相同）。`
          : `数据集 ${data.dataset.source_name} 上传成功，请运行校验。`,
      )
      setFile(null)
      setSourceName('')
      setLegalBasis('')
    },
    onError: (error) =>
      setFormError(
        error instanceof ApiError
          ? `${error.code}：${error.message}`
          : '上传失败，请检查网络后重试。',
      ),
  })

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    setFormError(null)
    if (file === null) {
      setFormError('请选择 CSV 或 XLSX 文件。')
      return
    }
    if (!sourceName.trim() || !legalBasis.trim()) {
      setFormError('来源名称与合法性声明均为必填。')
      return
    }
    const form = new FormData()
    form.append('file', file)
    form.append('source_name', sourceName.trim())
    form.append('legal_basis', legalBasis.trim())
    form.append('source_type', 'analyst_upload')
    upload.mutate(form)
  }

  return (
    <form className="upload-form" onSubmit={onSubmit} aria-label="上传数据集">
      <div className="toolbar">
        <label className="file-label">
          选择文件
          <input
            type="file"
            accept=".csv,.xlsx"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </label>
        <input
          aria-label="来源名称"
          placeholder="来源名称，如：文旅局公开月报"
          value={sourceName}
          onChange={(event) => setSourceName(event.target.value)}
        />
        <input
          aria-label="合法性声明"
          placeholder="合法性声明，如：公开统计公报"
          value={legalBasis}
          onChange={(event) => setLegalBasis(event.target.value)}
        />
        <button type="submit" className="btn primary" disabled={upload.isPending}>
          {upload.isPending ? '上传中…' : '上传'}
        </button>
      </div>
      {file ? <p className="muted">已选择：{file.name}（{file.size} 字节）</p> : null}
      {formError ? (
        <p role="alert" className="form-error">
          {formError}
        </p>
      ) : null}
      <p className="muted contract-hint">
        数据合同：city_code、metric_date、metric_name、value、available_at 必填；
        source_url、published_at、observed_at 可选。仅接受 UTF-8 CSV 与 .xlsx。
      </p>
    </form>
  )
}

export function DataCenterPage() {
  const { hasRole } = useAuth()
  const [tab, setTab] = useState<'datasets' | 'cities'>('datasets')
  const [notice, setNotice] = useState<string | null>(null)
  const datasets = useQuery({ queryKey: ['datasets'], queryFn: listDatasets })
  const canAct = hasRole('analyst')

  return (
    <section className="page">
      <header>
        <p className="eyebrow">CITYPULSE / DATA CENTER</p>
        <h1>数据中心</h1>
        <p className="muted">
          上传与校验进入隔离区，全部阻断错误修复后才能提交为不可变数据版本；相同内容重复上传自动去重。
        </p>
      </header>

      <div className="tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'datasets'}
          className={tab === 'datasets' ? 'tab on' : 'tab'}
          onClick={() => setTab('datasets')}
        >
          数据集
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'cities'}
          className={tab === 'cities' ? 'tab on' : 'tab'}
          onClick={() => setTab('cities')}
        >
          城市目录
        </button>
      </div>

      {tab === 'datasets' ? (
        <>
          <UploadPanel onNotice={setNotice} />
          {notice ? (
            <p role="status" className="notice">
              {notice}
            </p>
          ) : null}
          {datasets.isPending ? <p className="muted">正在加载数据集…</p> : null}
          {datasets.isError ? <p role="alert">数据集加载失败，请稍后重试。</p> : null}
          {datasets.data ? (
            <table>
              <thead>
                <tr>
                  <th>数据集</th>
                  <th>状态</th>
                  <th>规模</th>
                  <th>SHA-256</th>
                  <th>上传时间</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {datasets.data.items.map((dataset) => (
                  <DatasetRow key={dataset.id} dataset={dataset} canAct={canAct} />
                ))}
                {datasets.data.items.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="muted">
                      还没有数据集。上传第一份文件开始数据接入流程。
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          ) : null}
        </>
      ) : (
        <CityCatalogPanel />
      )}
    </section>
  )
}
