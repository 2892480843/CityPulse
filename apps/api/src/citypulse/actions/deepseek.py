"""Optional DeepSeek call with strict JSON validation.

Any failure (missing key, timeout, malformed JSON, schema mismatch) returns
None so the caller falls back to the deterministic rule template.
"""

import json
from collections.abc import Callable
from typing import Any

from citypulse.actions.generator import GeneratedDraft
from citypulse.prediction.models import PredictionResult

TIMEOUT_SECONDS = 12.0

SYSTEM_PROMPT = (
    "你是文旅经营动作助手。只依据输入的城市信号与证据生成结构化动作草案，"
    "不得编造无法由输入支持的事实。只输出 JSON。"
)


def build_prompt(result: PredictionResult) -> str:
    factors = json.dumps(result.factors, ensure_ascii=False)
    return (
        f"城市：{result.city_name}（{result.city_code}）\n"
        f"趋势分：{result.trend_score}，风险压力：{result.risk_pressure}，"
        f"证据完整度：{result.evidence_coverage}，行动优先级：{result.action_priority}\n"
        f"因子：{factors}\n"
        "请输出 JSON，字段：target_segment(string), campaign_theme(string<=120字), "
        "supply_actions(array of string), assumptions(array of string), "
        "risk_notes(string)。不要输出其他内容。"
    )


def parse_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    segment = payload.get("target_segment")
    theme = payload.get("campaign_theme")
    if not isinstance(segment, str) or not segment.strip():
        return None
    if not isinstance(theme, str) or not theme.strip():
        return None
    for key in ("supply_actions", "assumptions"):
        value = payload.get(key)
        if value is not None and not (
            isinstance(value, list) and all(isinstance(item, str) for item in value)
        ):
            return None
    return payload


def request_json(
    post_json: Callable[..., Any],
    url: str,
    headers: dict[str, str],
    body: dict[str, Any],
) -> dict[str, Any] | None:
    try:
        response = post_json(url, headers=headers, body=body)
        content = response["choices"][0]["message"]["content"]
        return parse_payload(json.loads(content))
    except Exception:
        return None


def deepseek_draft(
    result: PredictionResult,
    *,
    api_key: str,
    base_url: str,
    post_json: Callable[..., Any],
) -> dict[str, Any] | None:
    if not api_key:
        return None
    payload = request_json(
        post_json,
        f"{base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        body={
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_prompt(result)},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        },
    )
    return payload


def merge_generated(base: GeneratedDraft, payload: dict[str, Any]) -> GeneratedDraft:
    return GeneratedDraft(
        target_segment=str(payload.get("target_segment", base.target_segment))[:120],
        action_window_start=base.action_window_start,
        action_window_end=base.action_window_end,
        product_bundle=base.product_bundle,
        campaign_theme=str(payload.get("campaign_theme", base.campaign_theme))[:300],
        supply_actions=list(payload.get("supply_actions") or base.supply_actions)[:8],
        assumptions=list(payload.get("assumptions") or base.assumptions)[:8],
        risk_notes=str(payload.get("risk_notes", base.risk_notes))[:1000],
    )
