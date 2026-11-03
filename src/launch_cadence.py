#!/usr/bin/env python3
"""Count launches per quarter by rocket family (Launch Library 2).

Uses a small number of API pages to stay under the free ~15 calls/hour limit.
Saves a chart to cadence.png in the project root.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "cadence.png"

# List mode + modest page size keeps each response small and total calls low.
BASE = (
    "https://ll.thespacedevs.com/2.2.0/launch/previous/"
    "?limit=100&net__gte=2024-01-01&mode=list"
)


def fetch_launches(max_rows: int = 400, max_pages: int = 4) -> list[dict]:
    """Fetch recent previous launches with a hard page cap (rate-limit safe)."""
    url = BASE
    rows: list[dict] = []
    pages = 0
    while url and len(rows) < max_rows and pages < max_pages:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        payload = resp.json()
        rows.extend(payload.get("results", []))
        url = payload.get("next")
        pages += 1
        print(f"page {pages}: {len(payload.get('results', []))} rows "
              f"(total {len(rows)})", flush=True)
    return rows[:max_rows]


def main() -> int:
    rows = fetch_launches()
    if not rows:
        print("No launches returned", file=sys.stderr)
        return 1

    records = []
    for x in rows:
        name = (x.get("name") or "").split("|")[0].strip()
        status = (x.get("status") or {}).get("abbrev", "")
        records.append({"date": x.get("net"), "rocket": name, "status": status})

    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    df = df.dropna(subset=["date"])
    # PeriodIndex drops tz; normalize to UTC-naive first
    df["q"] = df["date"].dt.tz_convert("UTC").dt.tz_localize(None).dt.to_period("Q")

    counts = df["rocket"].value_counts()
    print("\nTop rockets by launch count in fetched window:")
    print(counts.head(10).to_string())
    print(f"\nTotal rows used: {len(df)}")

    top = counts.head(6).index
    pivot = (
        df[df.rocket.isin(top)]
        .groupby(["q", "rocket"])
        .size()
        .unstack(fill_value=0)
    )
    ax = pivot.plot(marker="o", figsize=(10, 5))
    ax.set_title("Launches per quarter (top 6 rockets)")
    ax.set_xlabel("Quarter")
    ax.set_ylabel("Launches")
    plt.tight_layout()
    plt.savefig(OUT)
    print(f"\nWrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
