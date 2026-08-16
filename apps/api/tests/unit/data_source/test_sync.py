from datetime import date, timedelta
from pathlib import Path

import pytest

from citypulse.data_source.sync import comfort_fit, fetch_weather_rows, read_divisions

DIVISIONS = "code,name,province\n110100,北京市,北京市\n130100,石家庄,河北省\n"


def test_read_divisions_parses_snapshot(tmp_path: Path) -> None:
    snapshot = tmp_path / "admin_divisions_cn.csv"
    snapshot.write_text(DIVISIONS, encoding="utf-8")

    rows = read_divisions(snapshot)

    assert rows == [("110100", "北京市", "北京市"), ("130100", "石家庄", "河北省")]


def test_comfort_fit_peaks_in_mild_band() -> None:
    assert comfort_fit(24, 18, 0) == 100.0
    assert comfort_fit(10, 4, 0) == pytest.approx(46.0)
    assert comfort_fit(34, 28, 0) == pytest.approx(70.0)
    assert comfort_fit(24, 18, 15) == pytest.approx(60.0)


def test_fetch_weather_rows_geocodes_and_parses_archive() -> None:
    end = date(2026, 8, 15)
    days = [end - timedelta(days=offset) for offset in (1, 0)]

    def getter(url: str) -> dict:
        if "geocoding" in url:
            return {"results": [{"latitude": 42.9, "longitude": 129.5}]}
        return {
            "daily": {
                "time": [day.isoformat() for day in days],
                "temperature_2m_max": [23.0, 30.0],
                "temperature_2m_min": [17.0, 24.0],
                "precipitation_sum": [0.0, 5.0],
            }
        }

    rows = fetch_weather_rows("延吉", end_date=end, days=1, getter=getter)

    assert rows[-1][0] == end
    assert rows[-1][1] == comfort_fit(30.0, 24.0, 5.0)


def test_fetch_weather_rows_handles_unknown_city() -> None:
    rows = fetch_weather_rows(
        "不存在的地方", end_date=date(2026, 8, 15), getter=lambda url: {}
    )

    assert rows == []
