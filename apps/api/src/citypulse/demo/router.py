from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from citypulse.actions.models import ActionPlan
from citypulse.backtest.models import BacktestRun
from citypulse.city_catalog.models import City
from citypulse.data_source.models import DataSource
from citypulse.ingestion.models import Dataset, SignalObservation
from citypulse.prediction.models import PredictionResult, PredictionRun
from citypulse.shared.db import get_session

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])

DISCLAIMER = (
    "演示工作区：城市数值与曲线为方法演示样本（行政区划目录与 Open-Meteo 气象为真实开放数据），"
    "不构成真实预测；趋势分为排序分而非概率。"
)


class DemoResultItem(BaseModel):
    rank: int
    city_name: str
    province: str
    trend_score: float
    risk_pressure: float
    evidence_coverage: float
    action_priority: str
    momentum: float | None
    accelerating: bool


class DemoPlan(BaseModel):
    city_name: str
    status: str
    generator_type: str
    target_segment: str
    campaign_theme: str
    action_window: str
    supply_actions: list[str]
    risk_notes: str


class DemoSummary(BaseModel):
    disclaimer: str
    city_catalog_size: int
    dataset_count: int
    observation_count: int
    sources: list[dict[str, str | None]]
    latest_run: dict[str, object] | None
    leaderboard: list[DemoResultItem]
    latest_backtest: dict[str, object] | None
    featured_plans: list[DemoPlan]


@router.get("/summary", response_model=DemoSummary)
async def demo_summary(
    db: Annotated[AsyncSession, Depends(get_session)],
) -> DemoSummary:
    city_count = (await db.execute(select(func.count()).select_from(City))).scalar_one()
    dataset_count = (await db.execute(select(func.count()).select_from(Dataset))).scalar_one()
    observation_count = (
        await db.execute(select(func.count()).select_from(SignalObservation))
    ).scalar_one()
    sources = [
        {
            "label": source.label,
            "kind": source.kind,
            "last_synced_at": source.last_synced_at.isoformat() if source.last_synced_at else None,
            "last_status": source.last_status,
        }
        for source in (
            await db.execute(select(DataSource).order_by(DataSource.kind))
        ).scalars()
    ]

    run = (
        await db.execute(
            select(PredictionRun)
            .where(PredictionRun.status == "succeeded")
            .order_by(sa.desc(PredictionRun.created_at))
            .limit(1)
        )
    ).scalars().first()
    leaderboard: list[DemoResultItem] = []
    latest_run: dict[str, object] | None = None
    if run is not None:
        latest_run = {
            "id": str(run.id),
            "window_days": run.window_days,
            "as_of_date": run.as_of_date.isoformat(),
            "city_count": run.city_count,
            "created_at": run.created_at.isoformat(),
        }
        results = (
            await db.execute(
                select(PredictionResult)
                .where(PredictionResult.run_id == run.id)
                .order_by(PredictionResult.trend_rank)
                .limit(13)
            )
        ).scalars().all()
        leaderboard = [
            DemoResultItem(
                rank=item.trend_rank,
                city_name=item.city_name,
                province=item.province,
                trend_score=item.trend_score,
                risk_pressure=item.risk_pressure,
                evidence_coverage=item.evidence_coverage,
                action_priority=item.action_priority,
                momentum=item.momentum,
                accelerating=item.accelerating,
            )
            for item in results
        ]

    backtest = (
        await db.execute(
            select(BacktestRun)
            .where(BacktestRun.status == "succeeded")
            .order_by(sa.desc(BacktestRun.created_at))
            .limit(1)
        )
    ).scalars().first()
    latest_backtest: dict[str, object] | None = None
    if backtest is not None and backtest.metrics:
        metrics = backtest.metrics
        latest_backtest = {
            "t0": backtest.t0.isoformat(),
            "targets": backtest.target_city_codes,
            "controls": backtest.control_city_codes,
            "hit_at_5": metrics.get("hit_at_5"),
            "hit_at_5_note": metrics.get("hit_at_5_note"),
            "mean_lead_days": metrics.get("mean_lead_days"),
            "false_alerts_per_100": metrics.get("false_alerts_per_100"),
            "evidence_coverage": metrics.get("evidence_coverage"),
            "snapshots": [
                {
                    "offset_days": snapshot["offset_days"],
                    "ranking": snapshot["ranking"][:5],
                }
                for snapshot in metrics.get("snapshots", [])
            ],
        }

    plans = (
        await db.execute(
            select(ActionPlan)
            .where(ActionPlan.status.in_(("approved", "pending_review")))
            .order_by(sa.desc(ActionPlan.created_at))
            .limit(3)
        )
    ).scalars().all()
    featured: list[DemoPlan] = [
        DemoPlan(
            city_name=plan.city_name,
            status=plan.status,
            generator_type=plan.generator_type,
            target_segment=plan.target_segment,
            campaign_theme=plan.campaign_theme,
            action_window=f"{plan.action_window_start} ~ {plan.action_window_end}",
            supply_actions=plan.supply_actions,
            risk_notes=plan.risk_notes,
        )
        for plan in plans
    ]

    return DemoSummary(
        disclaimer=DISCLAIMER,
        city_catalog_size=city_count,
        dataset_count=dataset_count,
        observation_count=observation_count,
        sources=sources,
        latest_run=latest_run,
        leaderboard=leaderboard,
        latest_backtest=latest_backtest,
        featured_plans=featured,
    )
