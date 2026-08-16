"""Optional Feishu group notification for approved action plans.

Posts an interactive card to a Feishu custom bot webhook when configured
via CITYPULSE_FEISHU_WEBHOOK. Failures are swallowed and logged so the
review flow never blocks on IM delivery.
"""

import json
import urllib.request

from citypulse.actions.models import ActionPlan

TIMEOUT_SECONDS = 8.0


def build_card(plan: ActionPlan) -> dict[str, object]:
    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"CityPulse 动作方案已批准 · {plan.city_name}",
                },
                "template": "green",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"**目标客群**：{plan.target_segment}\n"
                            f"**行动窗口**：{plan.action_window_start} ~ {plan.action_window_end}\n"
                            f"**投放主题**：{plan.campaign_theme}\n"
                            f"**生成方式**：{plan.generator_type}"
                        ),
                    },
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**供给动作**：{'；'.join(plan.supply_actions[:3])}",
                    },
                },
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": (
                                "演示工作区数据为方法演示样本，不构成真实预测；"
                                "详情见平台经营动作页。"
                            ),
                        }
                    ],
                },
            ],
        },
    }


def notify(webhook_url: str, plan: ActionPlan) -> bool:
    if not webhook_url:
        return False
    try:
        request = urllib.request.Request(
            webhook_url,
            data=json.dumps(build_card(plan)).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = json.loads(response.read().decode("utf-8"))
        return body.get("code", 0) == 0 or body.get("StatusCode") == 0
    except Exception:
        return False
