#!/usr/bin/env python3
"""Aggregate NET slip by rocket (name prefix before " | ") across all consecutive snapshot pairs.

Writes data/slip_by_provider.csv: per rocket (the API's older list-mode snapshots
leave the provider field empty, so the rocket is parsed from the launch name),
timed observations tracked, how many slipped (later by ≥ 1 h), share slipped,
mean and max slip in days.

Launches already flown (status Success/Failure/Partial Failure) are excluded.
A comparison only counts when both NETs are timed to the hour or better;
placeholder dates are excluded (see precision.py).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from launch_slip import MIN_SLIP_DAYS, compare_frames

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def provider_slip(
    frames: list[pd.DataFrame],
    *,
    include_low_precision: bool = False,
    min_slip_days: float = MIN_SLIP_DAYS,
) -> pd.DataFrame:
    """Return per-rocket slip stats over consecutive pairs of snapshot frames."""
    parts = []
    for a, b in zip(frames, frames[1:]):
        m = compare_frames(a, b, include_low_precision=include_low_precision)
        if m.empty:
            continue
        name_col = "name_b" if "name_b" in m.columns else "name_a"
        m = m.copy()
        m["provider"] = m[name_col].astype(str).str.split(" | ", regex=False).str[0].str.strip()
        parts.append(m[["provider", "slip_days"]])
    empty_cols = ["provider", "observations", "slipped",
                  "share_slipped", "mean_slip_days", "max_slip_days"]
    if not parts:
        return pd.DataFrame(columns=empty_cols)
    allm = pd.concat(parts)
    g = allm.groupby("provider")["slip_days"]
    out = pd.DataFrame({
        "observations": g.size(),
        "slipped": g.apply(lambda s: int((s >= min_slip_days).sum())),
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
    df.to_csv(DATA / "slip_by_provider.csv", index=False, float_format="%.3f")
    print(f"{len(files)} snapshots, {len(files) - 1} pairs")
    print(df.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
