#!/usr/bin/env python3
"""Summarize launch slip across every consecutive pair of data/upcoming_*.csv snapshots.

Writes data/slip_summary.csv (one row per snapshot pair: matched launches,
timed comparisons, launches slipped, mean/median/max slip in days) and
slip_summary.png.

Only launches still upcoming at the later snapshot are included. A comparison
counts in the slip statistics only when both NETs are timed to the hour or
better; a slip is a later move of at least 1 hour. Placeholder dates are
excluded (see precision.py).
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from launch_slip import FLAG_OK, MIN_SLIP_DAYS, compare_frames_all

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

FILTER_NOTE = (
    "Timed NETs only (hour precision or better); slip = move later ≥ 1 h. "
    "Placeholder dates excluded. Data: Launch Library 2 (The Space Devs)."
)


def pair_stats(
    a: pd.DataFrame,
    b: pd.DataFrame,
    *,
    include_low_precision: bool = False,
    min_slip_days: float = MIN_SLIP_DAYS,
) -> dict:
    """Return slip statistics for one snapshot pair.

    ``matched`` is every still-upcoming launch present in both snapshots.
    Mean / median / max and ``slipped`` are computed on timed comparisons
    only (unless ``include_low_precision``).
    """
    all_rows = compare_frames_all(a, b)
    timed = all_rows[all_rows["precision_flag"] == FLAG_OK]
    used = all_rows if include_low_precision else timed
    slip = used["slip_days"] if len(used) else pd.Series(dtype=float)
    return {
        "matched": int(len(all_rows)),
        "timed": int(len(timed)),
        "excluded": int(len(all_rows) - len(timed)),
        "slipped": int((slip >= min_slip_days).sum()) if len(used) else 0,
        "mean_slip_days": round(float(slip.mean()), 3) if len(used) else 0.0,
        "median_slip_days": round(float(slip.median()), 3) if len(used) else 0.0,
        "max_slip_days": round(float(slip.max()), 3) if len(used) else 0.0,
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
    df.to_csv(DATA / "slip_summary.csv", index=False, float_format="%.3f")
    print(df.to_string(index=False))
    fig, ax = plt.subplots(figsize=(8, 4.4))
    ax.bar(df["to"], df["mean_slip_days"], label="mean")
    ax.plot(df["to"], df["max_slip_days"], "o-", color="C3", label="max")
    ax.set_ylabel("NET slip (days)")
    ax.set_title("Upcoming-launch slip between weekly snapshots")
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout(rect=(0, 0.10, 1, 1))
    fig.text(0.5, 0.015, FILTER_NOTE, ha="center", va="bottom", fontsize=8, color="0.35")
    fig.savefig(ROOT / "slip_summary.png", dpi=120)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
