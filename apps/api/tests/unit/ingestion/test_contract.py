from citypulse.ingestion.contract import validate_observations

KNOWN_CITIES = {"222401", "370300"}

HEADER = "city_code,metric_date,metric_name,value,available_at,source_url,published_at,observed_at"


def rows_from(lines: list[str]) -> list[dict[str, str | None]]:
    import csv
    import io

    return list(csv.DictReader(io.StringIO("\n".join(lines))))


def test_valid_rows_parse_with_metadata() -> None:
    rows = rows_from(
        [
            HEADER,
            "222401,2026-07-01,content_growth,40.5,2026-07-02T08:00:00+08:00,https://a.example/x,2026-07-01T18:00:00+08:00,2026-07-02T08:00:00+08:00",
            "222401,2026-07-02,content_growth,42.5,2026-07-03T08:00:00+08:00,https://a.example/x,2026-07-02T18:00:00+08:00,2026-07-03T08:00:00+08:00",
        ]
    )

    observations, report = validate_observations(rows, known_city_codes=KNOWN_CITIES)

    assert report.is_valid
    assert report.row_count == 2
    assert report.city_count == 1
    assert str(report.metric_date_min) == "2026-07-01"
    assert str(report.metric_date_max) == "2026-07-02"
    assert len(observations) == 2
    assert observations[0].value == 40.5


def test_missing_required_column_is_blocking() -> None:
    rows = rows_from(
        ["city_code,metric_date,metric_name,value", "222401,2026-07-01,content_growth,4"]
    )

    observations, report = validate_observations(rows, known_city_codes=KNOWN_CITIES)

    assert not report.is_valid
    assert observations == []
    assert report.errors[0].code == "MISSING_COLUMN"
    assert report.errors[0].column == "available_at"


def test_empty_file_is_blocking() -> None:
    observations, report = validate_observations([], known_city_codes=KNOWN_CITIES)

    assert not report.is_valid
    assert report.errors[0].code == "NO_DATA_ROWS"


def test_unknown_city_code_is_blocking() -> None:
    rows = rows_from(
        [
            HEADER,
            "999999,2026-07-01,content_growth,10,2026-07-02T08:00:00+08:00,,,,",
        ]
    )

    _, report = validate_observations(rows, known_city_codes=KNOWN_CITIES)

    assert report.errors[0].code == "UNKNOWN_CITY"


def test_unknown_metric_is_blocking() -> None:
    rows = rows_from(
        [
            HEADER,
            "222401,2026-07-01,vibe_score,10,2026-07-02T08:00:00+08:00,,,,",
        ]
    )

    _, report = validate_observations(rows, known_city_codes=KNOWN_CITIES)

    assert report.errors[0].code == "UNKNOWN_METRIC"


def test_duplicate_rows_are_blocking() -> None:
    line = "222401,2026-07-01,content_growth,10,2026-07-02T08:00:00+08:00,,,,"
    rows = rows_from([HEADER, line, line])

    _, report = validate_observations(rows, known_city_codes=KNOWN_CITIES)

    assert report.errors[0].code == "DUPLICATE_KEY"


def test_formula_values_are_blocking() -> None:
    rows = rows_from(
        [
            HEADER,
            "=SUM(A1),2026-07-01,content_growth,10,2026-07-02T08:00:00+08:00,,,,",
        ]
    )

    _, report = validate_observations(rows, known_city_codes=KNOWN_CITIES)

    assert report.errors[0].code == "FORMULA_VALUE"


def test_negative_values_are_accepted() -> None:
    rows = rows_from(
        [
            HEADER,
            "222401,2026-07-01,content_growth,-12.5,2026-07-02T08:00:00+08:00,,,,",
        ]
    )

    observations, report = validate_observations(rows, known_city_codes=KNOWN_CITIES)

    assert report.is_valid
    assert observations[0].value == -12.5


def test_published_after_available_is_blocking() -> None:
    rows = rows_from(
        [
            HEADER,
            "222401,2026-07-01,content_growth,10,2026-07-02T08:00:00+08:00,,2026-07-03T18:00:00+08:00,",
        ]
    )

    _, report = validate_observations(rows, known_city_codes=KNOWN_CITIES)

    assert report.errors[0].code == "PUBLISHED_AFTER_AVAILABLE"


def test_invalid_date_and_value_are_blocking() -> None:
    rows = rows_from(
        [
            HEADER,
            "222401,2026-13-45,content_growth,10,2026-07-02T08:00:00+08:00,,,,",
            "222401,2026-07-02,content_growth,NaN,2026-07-03T08:00:00+08:00,,,,",
        ]
    )

    _, report = validate_observations(rows, known_city_codes=KNOWN_CITIES)

    codes = {error.code for error in report.errors}
    assert codes == {"INVALID_DATE", "INVALID_VALUE"}


def test_missing_source_and_observed_times_raise_warnings_only() -> None:
    rows = rows_from(
        [
            HEADER,
            "222401,2026-07-01,content_growth,10,2026-07-02T08:00:00+08:00,,,",
        ]
    )

    observations, report = validate_observations(rows, known_city_codes=KNOWN_CITIES)

    assert report.is_valid
    assert observations
    warning_codes = {warning.code for warning in report.warnings}
    assert warning_codes == {"MISSING_SOURCE_URL", "MISSING_OBSERVED_AT"}


def test_date_coverage_gap_is_reported_as_warning() -> None:
    rows = rows_from(
        [
            HEADER,
            "222401,2026-07-01,content_growth,10,2026-07-02T08:00:00+08:00,,,,",
            "222401,2026-07-05,content_growth,12,2026-07-06T08:00:00+08:00,,,,",
        ]
    )

    _, report = validate_observations(rows, known_city_codes=KNOWN_CITIES)

    assert report.is_valid
    assert any(warning.code == "DATE_COVERAGE_GAP" for warning in report.warnings)
