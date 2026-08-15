import { getJson, patchJson, postJson } from '../../shared/api/client'
import type { ActionPlan, ActionPlanList } from '../../shared/api/types'

export const listPlans = (status?: string) =>
  getJson<ActionPlanList>(
    `/api/v1/action-plans${status ? `?status=${status}` : ''}`,
  )

export const generatePlan = (predictionResultId: string) =>
  postJson<ActionPlan>('/api/v1/action-plans', {
    prediction_result_id: predictionResultId,
  })

export const updatePlan = (id: string, payload: Record<string, unknown>) =>
  patchJson<ActionPlan>(`/api/v1/action-plans/${id}`, payload)

export const submitPlan = (id: string) =>
  postJson<ActionPlan>(`/api/v1/action-plans/${id}/submit`)

export const reviewPlan = (id: string, decision: 'approved' | 'rejected', comment: string) =>
  postJson<ActionPlan>(`/api/v1/action-plans/${id}/${decision}`, { comment })
