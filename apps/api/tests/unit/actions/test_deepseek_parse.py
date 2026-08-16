from citypulse.actions.deepseek import merge_generated, parse_payload, request_json
from citypulse.actions.generator import rule_draft


def _draft():
    from datetime import date

    from citypulse.prediction.models import PredictionResult

    result = PredictionResult(
        run_id="00000000-0000-0000-0000-000000000001",
        city_code="222401",
        city_name="延吉",
        province="吉林",
        trend_rank=1,
        trend_score=76.7,
        risk_pressure=28,
        evidence_coverage=1.0,
        action_priority="high",
        data_stale=False,
        factors={"content_growth": 84},
        blockers=[],
    )
    return rule_draft(result, as_of=date(2026, 8, 16))


def test_parse_payload_accepts_valid_json() -> None:
    payload = {
        "target_segment": "亲子客群",
        "campaign_theme": "边境小城美食之旅",
        "supply_actions": ["补库存"],
        "assumptions": ["假设扩散持续"],
        "risk_notes": "注意周末房价",
    }

    assert parse_payload(payload) == payload


def test_parse_payload_rejects_missing_required_fields() -> None:
    assert parse_payload({"target_segment": "", "campaign_theme": "x"}) is None
    assert parse_payload({"target_segment": "x"}) is None
    assert parse_payload("not-a-dict") is None


def test_parse_payload_rejects_wrong_list_types() -> None:
    payload = {
        "target_segment": "x",
        "campaign_theme": "y",
        "supply_actions": "not-a-list",
    }

    assert parse_payload(payload) is None


def test_request_json_returns_none_on_any_failure() -> None:
    def broken_post(*args: object, **kwargs: object) -> dict:
        raise TimeoutError("simulated timeout")

    def malformed(*args: object, **kwargs: object) -> dict:
        return {"choices": [{"message": {"content": "not json {"}}]}

    assert request_json(broken_post, "http://x", {}, {}) is None
    assert request_json(malformed, "http://x", {}, {}) is None


def test_merge_generated_keeps_window_and_falls_back_fields() -> None:
    base = _draft()
    merged = merge_generated(
        base,
        {"target_segment": "摄影客群", "campaign_theme": "秋日童话"},
    )

    assert merged.target_segment == "摄影客群"
    assert merged.campaign_theme == "秋日童话"
    assert merged.action_window_start == base.action_window_start
    assert merged.supply_actions == base.supply_actions
