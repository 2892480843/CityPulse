import math
from dataclasses import asdict, dataclass, field
from datetime import date, datetime

REQUIRED_COLUMNS: tuple[str, ...] = (
    "city_code",
    "metric_date",
    "metric_name",
    "value",
    "available_at",
)
OPTIONAL_COLUMNS: tuple[str, ...] = ("source_url", "published_at", "observed_at")

ALLOWED_METRICS: frozenset[str] = frozenset(
    {
        "content_growth",
        "search_growth",
        "event_trigger",
        "accessibility",
        "supply_capacity",
        "weather_fit",
        "novelty",
        "cross_region_spread",
        "risk_pressure",
        "composite_score",
    }
)

FORMULA_PREFIXES: tuple[str, ...] = ("=", "+", "-", "@")

MAX_REPORT_ISSUES = 200


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    message: str
    row: int | None = None
    column: str | None = None


@dataclass(slots=True)
class ParsedObservation:
    city_code: str
    metric_date: date
    metric_name: str
    value: float
    source_url: str | None
    published_at: datetime | None
    observed_at: datetime | None
    available_at: datetime


@dataclass(slots=True)
class ValidationReport:
    row_count: int = 0
    city_count: int = 0
    metric_date_min: date | None = None
    metric_date_max: date | None = None
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "row_count": self.row_count,
            "city_count": self.city_count,
            "metric_date_min": self.metric_date_min.isoformat()
            if self.metric_date_min
            else None,
            "metric_date_max": self.metric_date_max.isoformat()
            if self.metric_date_max
            else None,
            "errors": [asdict(issue) for issue in self.errors],
            "warnings": [asdict(issue) for issue in self.warnings],
        }

    @property
    def is_valid(self) -> bool:
        return not self.errors


def _parse_date(raw: str) -> date | None:
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _parse_datetime(raw: str) -> datetime | None:
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _looks_like_formula(raw: str) -> bool:
    return raw.startswith(FORMULA_PREFIXES)


def validate_observations(
    rows: list[dict[str, str | None]],
    *,
    known_city_codes: set[str],
) -> tuple[list[ParsedObservation], ValidationReport]:
    report = ValidationReport()
    if not rows:
        report.errors.append(
            ValidationIssue(code="NO_DATA_ROWS", message="The file contains no data rows.")
        )
        return [], report

    header = {key for key in rows[0] if key is not None}
    for column in REQUIRED_COLUMNS:
        if column not in header:
            report.errors.append(
                ValidationIssue(
                    code="MISSING_COLUMN",
                    message=f"Required column '{column}' is missing.",
                    column=column,
                )
            )
    if report.errors:
        return [], report

    parsed: list[ParsedObservation] = []
    seen_keys: set[tuple[str, date, str]] = set()
    city_codes: set[str] = set()
    dates: set[date] = set()

    for index, row in enumerate(rows, start=2):
        if len(report.errors) >= MAX_REPORT_ISSUES:
            break

        city_code = (row.get("city_code") or "").strip()
        metric_name = (row.get("metric_name") or "").strip()
        raw_value = (row.get("value") or "").strip()
        raw_date = (row.get("metric_date") or "").strip()
        raw_available = (row.get("available_at") or "").strip()

        if not city_code or not metric_name or not raw_value or not raw_date or not raw_available:
            report.errors.append(
                ValidationIssue(
                    code="EMPTY_REQUIRED_CELL",
                    message="A required cell is empty.",
                    row=index,
                )
            )
            continue

        row_rejected = False
        for column, raw in (
            ("city_code", city_code),
            ("metric_name", metric_name),
            ("source_url", row.get("source_url") or ""),
        ):
            if raw and _looks_like_formula(raw.strip()):
                report.errors.append(
                    ValidationIssue(
                        code="FORMULA_VALUE",
                        message="Cell content looks like a formula and is rejected.",
                        row=index,
                        column=column,
                    )
                )
                row_rejected = True
        if row_rejected:
            continue

        metric_date = _parse_date(raw_date)
        if metric_date is None:
            report.errors.append(
                ValidationIssue(
                    code="INVALID_DATE",
                    message=f"'{raw_date}' is not an ISO date (YYYY-MM-DD).",
                    row=index,
                    column="metric_date",
                )
            )
            continue

        available_at = _parse_datetime(raw_available)
        if available_at is None:
            report.errors.append(
                ValidationIssue(
                    code="INVALID_TIMESTAMP",
                    message=f"'{raw_available}' is not an ISO timestamp.",
                    row=index,
                    column="available_at",
                )
            )
            continue

        try:
            value = float(raw_value)
        except ValueError:
            report.errors.append(
                ValidationIssue(
                    code="INVALID_VALUE",
                    message=f"'{raw_value}' is not a number.",
                    row=index,
                    column="value",
                )
            )
            continue
        if not math.isfinite(value):
            report.errors.append(
                ValidationIssue(
                    code="INVALID_VALUE",
                    message="The value must be a finite number.",
                    row=index,
                    column="value",
                )
            )
            continue

        if metric_name not in ALLOWED_METRICS:
            report.errors.append(
                ValidationIssue(
                    code="UNKNOWN_METRIC",
                    message=f"Metric '{metric_name}' is not part of the data contract.",
                    row=index,
                    column="metric_name",
                )
            )
            continue

        if city_code not in known_city_codes:
            report.errors.append(
                ValidationIssue(
                    code="UNKNOWN_CITY",
                    message=f"City code '{city_code}' is not present in the city catalog.",
                    row=index,
                    column="city_code",
                )
            )
            continue

        raw_published = (row.get("published_at") or "").strip()
        published_at = _parse_datetime(raw_published) if raw_published else None
        if raw_published and published_at is None:
            report.errors.append(
                ValidationIssue(
                    code="INVALID_TIMESTAMP",
                    message=f"'{raw_published}' is not an ISO timestamp.",
                    row=index,
                    column="published_at",
                )
            )
            continue
        if published_at is not None and published_at > available_at:
            report.errors.append(
                ValidationIssue(
                    code="PUBLISHED_AFTER_AVAILABLE",
                    message="published_at must not be later than available_at.",
                    row=index,
                    column="published_at",
                )
            )
            continue

        raw_observed = (row.get("observed_at") or "").strip()
        observed_at = _parse_datetime(raw_observed) if raw_observed else None
        if raw_observed and observed_at is None:
            report.errors.append(
                ValidationIssue(
                    code="INVALID_TIMESTAMP",
                    message=f"'{raw_observed}' is not an ISO timestamp.",
                    row=index,
                    column="observed_at",
                )
            )
            continue

        key = (city_code, metric_date, metric_name)
        if key in seen_keys:
            report.errors.append(
                ValidationIssue(
                    code="DUPLICATE_KEY",
                    message=f"Duplicate city/date/metric row for {city_code} "
                    f"{metric_date.isoformat()} {metric_name}.",
                    row=index,
                )
            )
            continue
        seen_keys.add(key)
        city_codes.add(city_code)
        dates.add(metric_date)

        if not (row.get("source_url") or "").strip():
            report.warnings.append(
                ValidationIssue(
                    code="MISSING_SOURCE_URL",
                    message="Row has no source_url; evidence coverage will drop.",
                    row=index,
                )
            )
        if not raw_observed:
            report.warnings.append(
                ValidationIssue(
                    code="MISSING_OBSERVED_AT",
                    message="Row has no observed_at capture time.",
                    row=index,
                )
            )

        parsed.append(
            ParsedObservation(
                city_code=city_code,
                metric_date=metric_date,
                metric_name=metric_name,
                value=value,
                source_url=(row.get("source_url") or "").strip() or None,
                published_at=published_at,
                observed_at=observed_at,
                available_at=available_at,
            )
        )

    if dates and not report.errors:
        report.metric_date_min = min(dates)
        report.metric_date_max = max(dates)
        ordered = sorted(dates)
        for previous, current in zip(ordered, ordered[1:], strict=False):
            if (current - previous).days > 1:
                report.warnings.append(
                    ValidationIssue(
                        code="DATE_COVERAGE_GAP",
                        message=f"Date coverage jumps from {previous.isoformat()} "
                        f"to {current.isoformat()}.",
                    )
                )
                break

    report.row_count = len(rows)
    report.city_count = len(city_codes)
    if report.errors:
        return [], report
    return parsed, report
