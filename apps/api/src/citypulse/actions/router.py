import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from citypulse.actions import service
from citypulse.actions.schemas import (
    ActionGenerateRequest,
    ActionPlanListResponse,
    ActionPlanUpdateRequest,
    ActionPlanVersionsResponse,
    ActionPlanVersionView,
    ActionPlanView,
    ReviewRequest,
)
from citypulse.audit import service as audit
from citypulse.identity.rbac import Identity, require_roles
from citypulse.jobs.service import record_job
from citypulse.shared.db import get_session
from citypulse.shared.errors import AppError

router = APIRouter(prefix="/api/v1/action-plans", tags=["actions"])


def _view(plan) -> ActionPlanView:
    return ActionPlanView.model_validate(plan)


@router.post("", response_model=ActionPlanView, status_code=201)
async def generate(
    payload: ActionGenerateRequest,
    identity: Annotated[Identity, Depends(require_roles("analyst", "operator"))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> ActionPlanView:
    plan = await service.generate_plan(
        db, prediction_result_id=payload.prediction_result_id, identity=identity
    )
    await record_job(
        db,
        job_type="action_generation",
        status="succeeded",
        created_by=identity.user_id,
        ref_type="action_plan",
        ref_id=plan.id,
        summary=f"{plan.city_name} via {plan.generator_type}",
    )
    await audit.record(
        db,
        action="action_plan_generated",
        object_type="action_plan",
        object_id=str(plan.id),
        actor_id=identity.user_id,
        actor_username=identity.username,
        detail={"city": plan.city_name, "generator": plan.generator_type},
    )
    await db.commit()
    return _view(plan)


@router.get("", response_model=ActionPlanListResponse)
async def list_plans(
    _identity: Annotated[Identity, Depends(require_roles("admin", "analyst", "operator"))],
    db: Annotated[AsyncSession, Depends(get_session)],
    status: (
        Annotated[
            Literal["draft", "pending_review", "approved", "rejected", "archived"] | None,
            Query(),
        ]
    ) = None,
) -> ActionPlanListResponse:
    plans = await service.list_plans(db, status=status)
    items = [_view(plan) for plan in plans]
    return ActionPlanListResponse(items=items, total=len(items))


@router.get("/{plan_id}/versions", response_model=ActionPlanVersionsResponse)
async def plan_versions(
    plan_id: uuid.UUID,
    _identity: Annotated[Identity, Depends(require_roles("admin", "analyst", "operator"))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> ActionPlanVersionsResponse:
    plan = await service.get_plan(db, plan_id)
    versions = await service.list_plan_versions(db, plan.id)
    items = [ActionPlanVersionView.model_validate(version) for version in versions]
    return ActionPlanVersionsResponse(items=items, total=len(items))


@router.get("/{plan_id}", response_model=ActionPlanView)
async def get_plan(
    plan_id: uuid.UUID,
    _identity: Annotated[Identity, Depends(require_roles("admin", "analyst", "operator"))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> ActionPlanView:
    return _view(await service.get_plan(db, plan_id))


@router.patch("/{plan_id}", response_model=ActionPlanView)
async def update_plan(
    plan_id: uuid.UUID,
    payload: ActionPlanUpdateRequest,
    identity: Annotated[Identity, Depends(require_roles("analyst", "operator"))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> ActionPlanView:
    plan = await service.update_plan(
        db,
        await service.get_plan(db, plan_id),
        target_segment=payload.target_segment,
        campaign_theme=payload.campaign_theme,
        risk_notes=payload.risk_notes,
        action_window_start=payload.action_window_start,
        action_window_end=payload.action_window_end,
        supply_actions=payload.supply_actions,
    )
    await audit.record(
        db,
        action="action_plan_edited",
        object_type="action_plan",
        object_id=str(plan.id),
        actor_id=identity.user_id,
        actor_username=identity.username,
    )
    await db.commit()
    return _view(plan)


@router.post("/{plan_id}/submit", response_model=ActionPlanView)
async def submit_plan(
    plan_id: uuid.UUID,
    identity: Annotated[Identity, Depends(require_roles("analyst", "operator"))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> ActionPlanView:
    plan = await service.submit_plan(db, await service.get_plan(db, plan_id), identity=identity)
    await audit.record(
        db,
        action="action_plan_submitted",
        object_type="action_plan",
        object_id=str(plan.id),
        actor_id=identity.user_id,
        actor_username=identity.username,
    )
    await db.commit()
    return _view(plan)


@router.post("/{plan_id}/approve", response_model=ActionPlanView)
async def approve_plan(
    plan_id: uuid.UUID,
    payload: ReviewRequest,
    identity: Annotated[Identity, Depends(require_roles("operator"))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> ActionPlanView:
    plan = await service.get_plan(db, plan_id)
    if plan.status != "pending_review":
        raise AppError(
            code="PLAN_NOT_PENDING",
            message="Only plans in pending_review can be approved.",
            status_code=409,
        )
    plan = await service.review_plan(
        db, plan, decision="approved", comment=payload.comment, identity=identity
    )
    await audit.record(
        db,
        action="action_plan_approved",
        object_type="action_plan",
        object_id=str(plan.id),
        actor_id=identity.user_id,
        actor_username=identity.username,
        detail={"comment": payload.comment},
    )
    await db.commit()
    return _view(plan)


@router.post("/{plan_id}/reject", response_model=ActionPlanView)
async def reject_plan(
    plan_id: uuid.UUID,
    payload: ReviewRequest,
    identity: Annotated[Identity, Depends(require_roles("operator"))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> ActionPlanView:
    plan = await service.get_plan(db, plan_id)
    if plan.status != "pending_review":
        raise AppError(
            code="PLAN_NOT_PENDING",
            message="Only plans in pending_review can be rejected.",
            status_code=409,
        )
    plan = await service.review_plan(
        db, plan, decision="rejected", comment=payload.comment, identity=identity
    )
    await audit.record(
        db,
        action="action_plan_rejected",
        object_type="action_plan",
        object_id=str(plan.id),
        actor_id=identity.user_id,
        actor_username=identity.username,
        detail={"comment": payload.comment},
    )
    await db.commit()
    return _view(plan)
