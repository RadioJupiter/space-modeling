#!/usr/bin/env python3
"""Aggregate NET slip by rocket (name prefix before " | ") across all consecutive snapshot pairs.

Writes data/slip_by_provider.csv: per rocket (the API's list mode leaves the
provider field empty, so the rocket is parsed from the launch name), launch-observations tracked,
how many slipped (>0.01 d), share slipped, mean and max slip in days.
Launches already flown (status Success/Failure/Partial Failure) are excluded.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DONE = {"Success", "Failure", "Partial Failure"}


def provider_slip(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Return per-provider slip stats over consecutive pairs of snapshot frames."""
    parts = []
    for a, b in zip(frames, frames[1:]):
        a = a.assign(net=pd.to_datetime(a["net"], utc=True))
        b = b.assign(net=pd.to_datetime(b["net"], utc=True))
        m = a[["id", "net"]].merge(b[["id", "net", "status", "name"]],
                                   on="id", suffixes=("_a", "_b"))
        m = m[~m["status"].isin(DONE)]
        m["provider"] = m["name"].astype(str).str.split(" | ", regex=False).str[0].str.strip()
        m["slip_days"] = (m["net_b"] - m["net_a"]).dt.total_seconds() / 86400.0
        parts.append(m[["provider", "slip_days"]])
    if not parts:
        return pd.DataFrame(columns=["provider", "observations", "slipped",
                                     "share_slipped", "mean_slip_days", "max_slip_days"])
    allm = pd.concat(parts)
    g = allm.groupby("provider")["slip_days"]
    out = pd.DataFrame({
        "observations": g.size(),
        "slipped": g.apply(lambda s: int((s > 0.01).sum())),
        "mean_slip_days": g.mean().round(3),
        "max_slip_days": g.max().round(3),
    })
    out["share_slipped"] = (out["slipped"] / out["observations"]).round(3)
    out = out[["observations", "slipped", "share_slipped", "mean_slip_days", "max_slip_days"]]
    return out.sort_values(["mean_slip_days", "observations"], ascending=False).reset_index()


def main() -> int:
    files = sorted(DATA.glob("upcoming_*.csv"))
    if len(files) < 2:
        print("Need at least two snapshots.")
        return 1
    df = provider_slip([pd.read_csv(f) for f in files])
    df.to_csv(DATA / "slip_by_provider.csv", index=False)
    print(f"{len(files)} snapshots, {len(files) - 1} pairs")
    print(df.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
