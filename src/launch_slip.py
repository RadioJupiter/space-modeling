#!/usr/bin/env python3
"""Snapshot upcoming launches and measure how far NET dates slip over time.

Each run writes data/upcoming_YYYY-MM-DD.csv.  Pass --diff A B to compare two
snapshots and report days of slip per launch (positive = delayed).
Over weeks this builds a rocket-shortage / schedule-pressure dataset.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
URL = "https://ll.thespacedevs.com/2.2.0/launch/upcoming/?limit=50&mode=list"


def snapshot() -> Path:
    DATA.mkdir(parents=True, exist_ok=True)
    resp = requests.get(URL, timeout=60)
    resp.raise_for_status()
    results = resp.json().get("results", [])
    rows = [
        {
            "id": x.get("id"),
            "name": x.get("name"),
            "net": x.get("net"),
            "status": (x.get("status") or {}).get("abbrev", ""),
            "provider": ((x.get("launch_service_provider") or {}).get("name")
                         if isinstance(x.get("launch_service_provider"), dict)
                         else ""),
        }
        for x in results
    ]
    up = pd.DataFrame(rows)
    now = pd.Timestamp.now(tz="UTC")
    up["net"] = pd.to_datetime(up["net"], utc=True, errors="coerce")
    up["days_out"] = (up["net"] - now).dt.total_seconds() / 86400.0
    today = pd.Timestamp.today().strftime("%Y-%m-%d")
    path = DATA / f"upcoming_{today}.csv"
    # Keep net as ISO string for stable diffs
    out = up.copy()
    out["net"] = out["net"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    out.to_csv(path, index=False)
    print(f"Wrote {path} ({len(out)} launches)")
    print("\nNext launches:")
    print(out[["name", "net", "status", "days_out"]].head(10).to_string(index=False))
    return path


def diff_snapshots(path_a: Path, path_b: Path) -> pd.DataFrame:
    """Compare two dated CSVs; positive slip_days means NET moved later."""
    a = pd.read_csv(path_a)
    b = pd.read_csv(path_b)
    a["net"] = pd.to_datetime(a["net"], utc=True)
    b["net"] = pd.to_datetime(b["net"], utc=True)
    # Prefer stable id when present; fall back to name
    key = "id" if "id" in a.columns and a["id"].notna().any() else "name"
    merged = a[[key, "name", "net"]].merge(
        b[[key, "net"]], on=key, how="inner", suffixes=("_a", "_b")
    )
    merged["slip_days"] = (merged["net_b"] - merged["net_a"]).dt.total_seconds() / 86400.0
    merged = merged.sort_values("slip_days", ascending=False)
    print(f"Compared {path_a.name} -> {path_b.name}: {len(merged)} matched launches")
    print(merged[["name", "net_a", "net_b", "slip_days"]].head(20).to_string(index=False))
    return merged


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--diff", nargs=2, metavar=("A", "B"),
                   help="Two CSV paths (or filenames under data/) to compare")
    args = p.parse_args()
    if args.diff:
        a, b = (Path(x) for x in args.diff)
        if not a.is_file():
            a = DATA / a.name
        if not b.is_file():
            b = DATA / b.name
        diff_snapshots(a, b)
        return 0
    snapshot()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
