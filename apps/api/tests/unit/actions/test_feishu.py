from datetime import date

from citypulse.actions.feishu import build_card, notify
from citypulse.actions.models import ActionPlan


def make_plan() -> ActionPlan:
    return ActionPlan(
        prediction_result_id="00000000-0000-0000-0000-000000000001",
        run_id="00000000-0000-0000-0000-000000000002",
        city_code="222401",
        city_name="延吉",
        status="approved",
        generator_type="deepseek",
        target_segment="25 岁以下及大学生客群优先",
        action_window_start=date(2026, 8, 18),
        action_window_end=date(2026, 9, 1),
        campaign_theme="边境小城美食之旅",
        supply_actions=["直达交通上线", "房价预警"],
        created_by="00000000-0000-0000-0000-000000000003",
    )


def test_card_carries_plan_facts_and_disclaimer() -> None:
    card = build_card(make_plan())

    assert card["msg_type"] == "interactive"
    content = str(card)
    assert "延吉" in content and "边境小城美食之旅" in content
    assert "不构成真实预测" in content


def test_notify_skips_without_webhook() -> None:
    assert notify("", make_plan()) is False


def test_notify_swallows_delivery_errors(monkeypatch) -> None:
    import urllib.request

    def broken(req, timeout=0):
        raise TimeoutError("boom")

    monkeypatch.setattr(urllib.request, "urlopen", broken)
    assert notify("https://open.feishu.cn/open-apis/bot/v2/hook/x", make_plan()) is False
