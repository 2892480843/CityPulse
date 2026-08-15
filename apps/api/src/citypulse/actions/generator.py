"""Deterministic rule templates; the mandatory fallback for action drafts."""

from dataclasses import dataclass
from datetime import date, timedelta

from citypulse.prediction.models import PredictionResult

HIGH_TEMPLATES = {
    "target_segment": "年轻情侣与摄影客群；文化、美食与城市叙事优先",
    "campaign_theme": "围绕城市独特叙事的抢先体验主题，避免重复通用标题",
    "supply_actions": [
        "核心客源地直达交通方案优先上线",
        "建立房价与库存预警，高风险日期采用观察阈值",
        "准备 2 天 1 夜与 3 天 2 夜线路模板",
    ],
    "assumptions": [
        "假设跨区域内容扩散持续到行动窗口结束",
        "假设供给承载在周末高峰前可完成补货",
    ],
    "risk_notes": "立即人工研判与备供；出现拥挤、价格越界或负面舆情时降级投放并复核。",
}

MEDIUM_TEMPLATES = {
    "target_segment": "小范围核心客群验证（单一客源地 + 单一主题）",
    "campaign_theme": "小流量验证主题，聚焦单一卖点",
    "supply_actions": ["仅锁定少量库存试点", "监测首批转化后再决定放量"],
    "assumptions": ["假设信号持续性需二次确认"],
    "risk_notes": "小范围验证；证据不足时退回观察池补充跨源确认。",
}

WATCH_TEMPLATES = {
    "target_segment": "暂不投放；积累跨源证据",
    "campaign_theme": "暂不生成投放主题",
    "supply_actions": ["补充事件、搜索与供给证据", "保持每周复核信号连续性"],
    "assumptions": ["假设当前信号仍可能是单源噪声"],
    "risk_notes": "继续观察与补证据；不进入任何投放或采购流程。",
}

BLOCKED_TEMPLATES = {
    "target_segment": "不适用；优先处置风险",
    "campaign_theme": "暂停一切主题生成",
    "supply_actions": ["启动风险处置与停止条件评估", "向运营负责人回报风险分项"],
    "assumptions": ["假设风险压力在处置前不会自行消退"],
    "risk_notes": "仅执行风险处置与停止条件；解除阻断前不得生成投放动作。",
}


@dataclass(frozen=True, slots=True)
class GeneratedDraft:
    target_segment: str
    action_window_start: date
    action_window_end: date
    product_bundle: list[dict[str, str]]
    campaign_theme: str
    supply_actions: list[str]
    assumptions: list[str]
    risk_notes: str


def rule_draft(result: PredictionResult, *, as_of: date) -> GeneratedDraft:
    templates = {
        "high": HIGH_TEMPLATES,
        "medium": MEDIUM_TEMPLATES,
        "watch": WATCH_TEMPLATES,
        "blocked": BLOCKED_TEMPLATES,
    }[result.action_priority]

    if result.action_priority == "high":
        start_offset, length = 3, 14
    elif result.action_priority == "medium":
        start_offset, length = 7, 7
    else:
        start_offset, length = 0, 0

    start = as_of + timedelta(days=start_offset)
    end = start + timedelta(days=length) if length else as_of

    top_factors = sorted(result.factors.items(), key=lambda item: item[1], reverse=True)[:3]
    accessibility = result.factors.get("accessibility", 0)
    leading = ", ".join(name for name, _value in top_factors)
    bundle = [
        {"type": "交通", "reason": f"可达性 {accessibility}", "priority": "P1"},
        {"type": "住宿", "reason": "供给预警与价格观察", "priority": "P2"},
        {"type": "内容", "reason": f"头部因子 {leading}", "priority": "P1"},
    ]

    return GeneratedDraft(
        target_segment=templates["target_segment"],
        action_window_start=start,
        action_window_end=end,
        product_bundle=bundle,
        campaign_theme=templates["campaign_theme"],
        supply_actions=templates["supply_actions"],
        assumptions=templates["assumptions"],
        risk_notes=templates["risk_notes"],
    )
