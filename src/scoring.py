#!/usr/bin/env python3
"""CityPulse transparent baseline scorer.

The bundled CSV is synthetic demo data. This script validates the data contract;
it is not a trained production model.
"""
from __future__ import annotations
import argparse, csv
from pathlib import Path

WEIGHTS = {
    "content_growth": 0.22,
    "search_growth": 0.18,
    "event_trigger": 0.12,
    "accessibility": 0.12,
    "supply_capacity": 0.10,
    "weather_fit": 0.08,
    "novelty": 0.08,
    "cross_region_spread": 0.10,
}
RISK_WEIGHT = 0.15

def city_score(row: dict[str, str]) -> float:
    value = sum(float(row[name]) * weight for name, weight in WEIGHTS.items())
    value -= float(row["risk_pressure"]) * RISK_WEIGHT
    return round(max(0.0, min(100.0, value)), 1)

def rank_file(input_path: Path, output_path: Path) -> None:
    with input_path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row["baseline_score"] = str(city_score(row))
    rows.sort(key=lambda row: float(row["baseline_score"]), reverse=True)
    for index, row in enumerate(rows, 1):
        row["baseline_rank"] = str(index)
    fields = ["baseline_rank", *[k for k in rows[0] if k != "baseline_rank"]]
    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

def main() -> None:
    parser = argparse.ArgumentParser(description="Rank CityPulse city signal rows")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, default=Path("ranked_output.csv"))
    args = parser.parse_args()
    rank_file(args.input, args.output)
    print(f"Wrote {args.output}")

if __name__ == "__main__":
    main()
