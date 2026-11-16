#!/usr/bin/env python3
"""Snapshot upcoming launches and measure how far NET dates slip over time.

Each run writes data/upcoming_YYYY-MM-DD.csv.  Pass --diff A B to compare two
snapshots and report days of slip per launch (positive = delayed).
Over weeks this builds a rocket-shortage / schedule-pressure dataset.

Placeholder (low-precision) NETs are not counted as slips. A comparison only
counts when both NETs are timed to the hour or better, and a slip is a later
move of at least 1 hour. See precision.py.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from precision import (
    FLAG_OK,
    MIN_SLIP_DAYS,
    MIN_SLIP_HOURS,
    precision_flag,
    resolve_class,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
# mode=normal includes window_start, window_end, net_precision, and provider.
URL = "https://ll.thespacedevs.com/2.2.0/launch/upcoming/?limit=50&mode=normal"
DONE = {"Success", "Failure", "Partial Failure"}


def _nested_name(obj: Any, *keys: str) -> str:
    """Walk nested dicts and return the final string value, or empty."""
    cur: Any = obj
    for key in keys:
        if not isinstance(cur, dict):
            return ""
        cur = cur.get(key)
    return cur if isinstance(cur, str) else ""


def normalize_launch(item: dict[str, Any]) -> dict[str, str]:
    """Flatten one Launch Library 2 launch object into a snapshot row."""
    provider = _nested_name(item, "launch_service_provider", "name")
    if not provider and isinstance(item.get("launch_service_provider"), str):
        provider = item["launch_service_provider"]
    status = _nested_name(item, "status", "abbrev") or _nested_name(item, "status", "name")
    return {
        "id": str(item.get("id") or ""),
        "name": str(item.get("name") or ""),
        "net": str(item.get("net") or ""),
        "status": status,
        "provider": provider,
        "window_start": str(item.get("window_start") or ""),
        "window_end": str(item.get("window_end") or ""),
        "net_precision": _nested_name(item, "net_precision", "name"),
    }


def snapshot() -> Path:
    DATA.mkdir(parents=True, exist_ok=True)
    resp = requests.get(URL, timeout=60)
    resp.raise_for_status()
    results = resp.json().get("results", [])
    up = pd.DataFrame([normalize_launch(x) for x in results])
    now = pd.Timestamp.now(tz="UTC")
    up["net"] = pd.to_datetime(up["net"], utc=True, errors="coerce")
    up["days_out"] = (up["net"] - now).dt.total_seconds() / 86400.0
    today = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d")
    path = DATA / f"upcoming_{today}.csv"
    out = up.copy()
    out["net"] = out["net"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    # Keep the historical column order, then the precision fields.
    cols = ["id", "name", "net", "status", "provider", "days_out",
            "window_start", "window_end", "net_precision"]
    for col in cols:
        if col not in out.columns:
            out[col] = ""
    out[cols].to_csv(path, index=False)
    print(f"Wrote {path} ({len(out)} launches)")
    print("\nNext launches:")
    print(out[["name", "net", "status", "days_out"]].head(10).to_string(index=False))
    return path


def _series_or_blank(df: pd.DataFrame, col: str) -> pd.Series:
    if col in df.columns:
        return df[col]
    return pd.Series([""] * len(df), index=df.index)


def annotate_precision(df: pd.DataFrame, net_col: str = "net") -> pd.DataFrame:
    """Add ``precision`` and ``precision_source`` using LL2 or the heuristic."""
    out = df.copy()
    classes: list[str] = []
    sources: list[str] = []
    for net, ws, we, prec in zip(
        out[net_col],
        _series_or_blank(out, "window_start"),
        _series_or_blank(out, "window_end"),
        _series_or_blank(out, "net_precision"),
    ):
        cls, src = resolve_class(net, ws, we, prec)
        classes.append(cls)
        sources.append(src)
    out["precision"] = classes
    out["precision_source"] = sources
    return out


def compare_frames(
    a: pd.DataFrame,
    b: pd.DataFrame,
    *,
    exclude_done: bool = True,
    include_low_precision: bool = False,
) -> pd.DataFrame:
    """Compare two snapshot frames; positive slip_days means NET moved later.

    Adds precision_a, precision_b, and precision_flag. Flown launches
    (Success / Failure / Partial Failure in the later snapshot) are dropped
    unless ``exclude_done`` is False. By default only rows whose two NETs are
    both timed (hour precision or better) are returned.
    """
    a = annotate_precision(a.copy())
    b = annotate_precision(b.copy())
    a["net"] = pd.to_datetime(a["net"], utc=True, errors="coerce")
    b["net"] = pd.to_datetime(b["net"], utc=True, errors="coerce")
    key = "id" if "id" in a.columns and a["id"].notna().any() else "name"
    a_keep = [c for c in [key, "name", "net", "precision", "status", "provider"] if c in a.columns]
    b_keep = [c for c in [key, "name", "net", "precision", "status", "provider"] if c in b.columns]
    # Avoid suffixing the join key itself.
    a_keep_unique = list(dict.fromkeys(a_keep))
    b_keep_unique = list(dict.fromkeys(b_keep))
    merged = a[a_keep_unique].merge(
        b[b_keep_unique], on=key, how="inner", suffixes=("_a", "_b")
    )
    # merge suffixes name/net/precision/status/provider; id stays unsuffixed.
    if "name_a" not in merged.columns and "name" in merged.columns:
        merged = merged.rename(columns={"name": "name_a"})
        merged["name_b"] = merged["name_a"]
    if exclude_done and "status_b" in merged.columns:
        merged = merged[~merged["status_b"].isin(DONE)].copy()
    elif exclude_done and "status" in merged.columns:
        merged = merged[~merged["status"].isin(DONE)].copy()
    net_a = merged["net_a"] if "net_a" in merged.columns else merged["net"]
    net_b = merged["net_b"] if "net_b" in merged.columns else merged["net"]
    merged["slip_days"] = (net_b - net_a).dt.total_seconds() / 86400.0
    pa = merged["precision_a"] if "precision_a" in merged.columns else merged["precision"]
    pb = merged["precision_b"] if "precision_b" in merged.columns else merged["precision"]
    merged["precision_flag"] = [precision_flag(x, y) for x, y in zip(pa, pb)]
    merged = merged.sort_values("slip_days", ascending=False, na_position="last")
    if include_low_precision:
        return merged.reset_index(drop=True)
    return merged[merged["precision_flag"] == FLAG_OK].reset_index(drop=True)


def compare_frames_all(
    a: pd.DataFrame,
    b: pd.DataFrame,
    *,
    exclude_done: bool = True,
) -> pd.DataFrame:
    """Like compare_frames, but keep low-precision and precision-change rows."""
    return compare_frames(a, b, exclude_done=exclude_done, include_low_precision=True)


def is_slip(slip_days: float, min_hours: float = MIN_SLIP_HOURS) -> bool:
    """True when a timed NET moved later by at least ``min_hours`` hours."""
    return pd.notna(slip_days) and slip_days >= (min_hours / 24.0)


def diff_snapshots(
    path_a: Path,
    path_b: Path,
    *,
    include_low_precision: bool = False,
) -> pd.DataFrame:
    """Compare two dated CSVs and print a precision-aware slip report."""
    a = pd.read_csv(path_a)
    b = pd.read_csv(path_b)
    all_rows = compare_frames_all(a, b)
    timed = all_rows[all_rows["precision_flag"] == FLAG_OK]
    excluded = all_rows[all_rows["precision_flag"] != FLAG_OK]
    print(
        f"Compared {path_a.name} -> {path_b.name}: "
        f"{len(all_rows)} matched, {len(timed)} timed, "
        f"{len(excluded)} excluded (placeholder / precision-change)"
    )
    name_col = "name_b" if "name_b" in all_rows.columns else "name_a"
    show_cols = [c for c in [name_col, "net_a", "net_b", "slip_days", "precision_flag"]
                 if c in all_rows.columns]

    slips = timed[timed["slip_days"] >= MIN_SLIP_DAYS]
    print(f"\nTimed slips (later by ≥ {MIN_SLIP_HOURS:g} h): {len(slips)}")
    if len(slips):
        print(slips[show_cols].to_string(index=False))

    minor = timed[(timed["slip_days"].abs() > 0) & (timed["slip_days"].abs() < MIN_SLIP_DAYS)]
    if len(minor):
        print(f"\nMinor adjustments (< {MIN_SLIP_HOURS:g} h): {len(minor)}")
        print(minor[show_cols].to_string(index=False))

    # Always list precision changes so placeholder artifacts stay visible.
    prec_changes = excluded[excluded["precision_flag"] == "precision_change"]
    if len(prec_changes):
        print(f"\nPrecision changes (not counted as slips): {len(prec_changes)}")
        print(prec_changes[show_cols].to_string(index=False))
    if include_low_precision:
        low = excluded[excluded["precision_flag"] == "low_precision"]
        if len(low):
            print(f"\nLow-precision comparisons (same placeholder class): {len(low)}")
            print(low[show_cols].to_string(index=False))
    return timed if not include_low_precision else all_rows


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--diff", nargs=2, metavar=("A", "B"),
                   help="Two CSV paths (or filenames under data/) to compare")
    p.add_argument("--include-low-precision", action="store_true",
                   help="Include placeholder / precision-change rows in the diff")
    args = p.parse_args()
    if args.diff:
        a, b = (Path(x) for x in args.diff)
        if not a.is_file():
            a = DATA / a.name
        if not b.is_file():
            b = DATA / b.name
        diff_snapshots(a, b, include_low_precision=args.include_low_precision)
        return 0
    snapshot()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
