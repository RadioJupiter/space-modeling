#!/usr/bin/env python3
"""Summarize launch slip across every consecutive pair of data/upcoming_*.csv snapshots.

Writes data/slip_summary.csv (one row per snapshot pair: matched launches,
launches slipped, mean/median/max slip in days) and slip_summary.png.
Only launches whose NET is still in the future at the later snapshot's start
are meaningful; launches that already flew are excluded via status.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DONE = {"Success", "Failure", "Partial Failure"}


def pair_stats(a: pd.DataFrame, b: pd.DataFrame) -> dict:
    a = a.assign(net=pd.to_datetime(a["net"], utc=True))
    b = b.assign(net=pd.to_datetime(b["net"], utc=True))
    m = a[["id", "net"]].merge(b[["id", "net", "status"]], on="id", suffixes=("_a", "_b"))
    m = m[~m["status"].isin(DONE)]
    slip = (m["net_b"] - m["net_a"]).dt.total_seconds() / 86400.0
    return {
        "matched": len(m),
        "slipped": int((slip > 0.01).sum()),
        "mean_slip_days": round(float(slip.mean()), 3) if len(m) else 0.0,
        "median_slip_days": round(float(slip.median()), 3) if len(m) else 0.0,
        "max_slip_days": round(float(slip.max()), 3) if len(m) else 0.0,
    }


def main() -> int:
    files = sorted(DATA.glob("upcoming_*.csv"))
    if len(files) < 2:
        print("Need at least two snapshots.")
        return 1
    rows = []
    for fa, fb in zip(files, files[1:]):
        s = pair_stats(pd.read_csv(fa), pd.read_csv(fb))
        rows.append({"from": fa.stem[9:], "to": fb.stem[9:], **s})
    df = pd.DataFrame(rows)
    df.to_csv(DATA / "slip_summary.csv", index=False)
    print(df.to_string(index=False))
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(df["to"], df["mean_slip_days"], label="mean")
    ax.plot(df["to"], df["max_slip_days"], "o-", color="C3", label="max")
    ax.set_ylabel("NET slip (days)")
    ax.set_title("Upcoming-launch slip between weekly snapshots")
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(ROOT / "slip_summary.png", dpi=120)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
