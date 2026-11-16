"""Placeholder / low-precision NET handling (no network)."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from launch_slip import compare_frames, compare_frames_all, is_slip, normalize_launch
from precision import (
    COARSE,
    DAY,
    TIMED,
    class_from_ll2,
    infer_class,
    precision_flag,
    resolve_class,
)
from slip_by_provider import provider_slip
from slip_history import pair_stats


def test_ll2_names_map_to_classes() -> None:
    assert class_from_ll2("Second") == TIMED
    assert class_from_ll2("Minute") == TIMED
    assert class_from_ll2("Hour") == TIMED
    assert class_from_ll2("Day") == DAY
    for name in ("Month", "Quarter 4", "Half 1", "Year", "Fiscal Year"):
        assert class_from_ll2(name) == COARSE
    assert class_from_ll2("") == ""
    assert class_from_ll2(None) == ""


def test_heuristic_month_day_and_timed() -> None:
    # Month placeholder: last day of month, midnight, zero-length window
    z = "2026-11-30T00:00:00Z"
    assert infer_class(z, z, z) == COARSE
    assert infer_class("2026-12-31T00:00:00Z") == COARSE  # year placeholder
    # Day placeholder: midnight, zero window, not month end
    d = "2026-11-13T00:00:00Z"
    assert infer_class(d, d, d) == DAY
    # Midnight but real window -> timed (a launch can open at 00:00 UTC)
    assert infer_class(d, d, "2026-11-13T04:00:00Z") == TIMED
    assert infer_class("2026-11-12T19:50:00Z", "", "") == TIMED
    assert infer_class("not a date") == "unknown"


def test_resolve_prefers_ll2_field() -> None:
    z = "2026-11-30T00:00:00Z"
    assert resolve_class(z, z, z, "Minute") == (TIMED, "ll2")
    assert resolve_class(z, z, z, "") == (COARSE, "heuristic")


def test_flags() -> None:
    assert precision_flag(TIMED, TIMED) == "ok"
    assert precision_flag(TIMED, COARSE) == "precision_change"
    assert precision_flag(COARSE, COARSE) == "low_precision"
    assert precision_flag(DAY, DAY) == "low_precision"


def test_normalize_captures_net_precision() -> None:
    row = normalize_launch(
        {"id": "x", "name": "A | B", "net": "2026-11-30T00:00:00Z",
         "net_precision": {"id": 7, "name": "Month", "abbrev": "MON"},
         "window_start": "2026-11-30T00:00:00Z",
         "window_end": "2026-11-30T00:00:00Z",
         "status": {"abbrev": "TBD"},
         "launch_service_provider": {"name": "SpaceX"}}
    )
    assert row["net_precision"] == "Month"
    assert row["provider"] == "SpaceX"
    assert row["window_start"] == "2026-11-30T00:00:00Z"
    assert normalize_launch({"id": "y"})["net_precision"] == ""


def test_compare_flags_placeholders() -> None:
    a = pd.DataFrame({
        "id": ["s1", "k1", "f1", "y1", "m1"],
        "name": ["Falcon 9 | Real", "Kuaizhou 11 | X", "Starship | Flight",
                 "Vulcan | Y", "Vulcan | M"],
        "net": [
            "2026-11-15T03:55:00Z",
            "2026-11-12T19:50:00Z",
            "2026-11-30T00:00:00Z",
            "2026-12-31T00:00:00Z",
            "2026-11-15T17:11:30Z",
        ],
        "window_start": [
            "2026-11-15T03:55:00Z",
            "2026-11-12T19:50:00Z",
            "2026-11-30T00:00:00Z",
            "2026-12-31T00:00:00Z",
            "2026-11-15T17:11:30Z",
        ],
        "window_end": [
            "2026-11-15T07:55:00Z",
            "2026-11-12T20:20:00Z",
            "2026-11-30T00:00:00Z",
            "2026-12-31T00:00:00Z",
            "2026-11-15T17:31:00Z",
        ],
    })
    b = pd.DataFrame({
        "id": ["s1", "k1", "f1", "y1", "m1"],
        "name": ["Falcon 9 | Real", "Kuaizhou 11 | X", "Starship | Flight",
                 "Vulcan | Y", "Vulcan | M"],
        "net": [
            "2026-11-16T03:55:00Z",
            "2026-11-30T00:00:00Z",
            "2026-11-13T00:00:00Z",
            "2026-12-31T00:00:00Z",
            "2026-11-15T17:40:30Z",
        ],
        "status": ["Go", "TBD", "TBD", "TBD", "Go"],
        "window_start": [
            "2026-11-16T03:55:00Z",
            "2026-11-30T00:00:00Z",
            "2026-11-13T00:00:00Z",
            "2026-12-31T00:00:00Z",
            "2026-11-15T17:11:30Z",
        ],
        "window_end": [
            "2026-11-16T07:55:00Z",
            "2026-11-30T00:00:00Z",
            "2026-11-13T00:00:00Z",
            "2026-12-31T00:00:00Z",
            "2026-11-15T17:40:30Z",
        ],
        "net_precision": ["Minute", "Month", "Day", "Year", "Second"],
    })
    delta = compare_frames_all(a, b).set_index("id")
    assert delta.loc["s1", "precision_flag"] == "ok"
    assert delta.loc["k1", "precision_flag"] == "precision_change"
    assert delta.loc["k1", "precision_a"] == TIMED
    assert delta.loc["k1", "precision_b"] == COARSE
    assert round(delta.loc["k1", "slip_days"], 2) == 17.17  # raw value kept, but flagged
    assert delta.loc["f1", "precision_flag"] == "precision_change"
    assert delta.loc["y1", "precision_flag"] == "low_precision"
    assert delta.loc["m1", "precision_flag"] == "ok"

    kept = compare_frames(a, b)
    assert set(kept["id"]) == {"s1", "m1"}
    assert len(compare_frames(a, b, include_low_precision=True)) == 5


def test_pair_stats_excludes_placeholder_mir_style() -> None:
    """A timed NET replaced by a month-end placeholder is not an 18-day slip."""
    a = pd.DataFrame({
        "id": ["mir", "f9"],
        "name": ["Mir | Demo Flight", "Falcon 9 Block 5 | USSF-317"],
        "net": ["2026-11-11T05:00:00Z", "2026-11-13T04:00:00Z"],
    })
    b = pd.DataFrame({
        "id": ["mir", "f9"],
        "name": ["Mir | Demo Flight", "Falcon 9 Block 5 | USSF-317"],
        "net": ["2026-11-30T00:00:00Z", "2026-11-19T04:00:00Z"],
        "status": ["TBD", "Go"],
    })
    s = pair_stats(a, b)
    assert s["matched"] == 2
    assert s["timed"] == 1
    assert s["excluded"] == 1
    assert s["slipped"] == 1
    assert s["max_slip_days"] == 6.0
    assert s["mean_slip_days"] == 6.0
    # Including placeholders would let the artifact dominate.
    raw = pair_stats(a, b, include_low_precision=True)
    assert raw["max_slip_days"] > 18


def test_provider_slip_excludes_placeholders() -> None:
    a = pd.DataFrame({
        "id": ["mir", "f9", "star"],
        "name": ["Mir | Demo", "Falcon 9 Block 5 | A", "Starship | Flight 15"],
        "net": ["2026-11-11T05:00:00Z", "2026-11-13T04:00:00Z", "2026-11-30T00:00:00Z"],
    })
    b = pd.DataFrame({
        "id": ["mir", "f9", "star"],
        "name": ["Mir | Demo", "Falcon 9 Block 5 | A", "Starship | Flight 15"],
        "net": ["2026-11-30T00:00:00Z", "2026-11-19T04:00:00Z", "2026-11-13T22:45:00Z"],
        "status": ["TBD", "Go", "TBC"],
    })
    r = provider_slip([a, b]).set_index("provider")
    assert "Mir" not in r.index  # timed -> month placeholder, excluded
    assert "Starship" not in r.index  # month placeholder -> timed, excluded
    assert list(r.index) == ["Falcon 9 Block 5"]
    assert r.loc["Falcon 9 Block 5", "observations"] == 1
    assert r.loc["Falcon 9 Block 5", "slipped"] == 1
    assert r.loc["Falcon 9 Block 5", "mean_slip_days"] == 6.0


def test_min_hours_threshold() -> None:
    assert is_slip(1.0 / 24.0) is True
    assert is_slip(0.9 / 24.0) is False
    assert is_slip(29.0 / 1440.0) is False  # 29 minutes
    assert is_slip(-2.0) is False  # pull-in is not a slip
    # A 29-minute T-0 tweak on launch day is a minor adjustment, not a slip.
    a = pd.DataFrame({"id": ["m1"], "name": ["Vulcan | M"], "net": ["2026-11-15T17:11:30Z"]})
    b = pd.DataFrame({"id": ["m1"], "name": ["Vulcan | M"],
                      "net": ["2026-11-15T17:40:30Z"], "status": ["Go"]})
    s = pair_stats(a, b)
    assert s["timed"] == 1 and s["slipped"] == 0
    assert s["max_slip_days"] == round(29.0 / 1440.0, 3)


def test_committed_snapshots_match_published_figures() -> None:
    """Lock the README / CSV headline numbers to the committed weekly snapshots."""
    data = Path(__file__).resolve().parents[1] / "data"
    files = sorted(data.glob("upcoming_*.csv"))
    assert [f.name for f in files] == [
        "upcoming_2026-11-02.csv",
        "upcoming_2026-11-09.csv",
        "upcoming_2026-11-16.csv",
    ]
    expected = [
        {"matched": 39, "timed": 7, "excluded": 32, "slipped": 2,
         "mean_slip_days": 1.142, "median_slip_days": 0.0, "max_slip_days": 7.0},
        {"matched": 41, "timed": 6, "excluded": 35, "slipped": 1,
         "mean_slip_days": 0.990, "median_slip_days": 0.0, "max_slip_days": 5.942},
    ]
    for (fa, fb), exp in zip(zip(files, files[1:]), expected):
        s = pair_stats(pd.read_csv(fa), pd.read_csv(fb))
        for key, val in exp.items():
            assert s[key] == val, f"{fa.stem}->{fb.stem} {key}: {s[key]} != {val}"

    by = provider_slip([pd.read_csv(f) for f in files]).set_index("provider")
    assert list(by.index) == [
        "Mir", "Falcon 9 Block 5", "Long March 12", "Long March 8A",
        "Soyuz 2.1b", "Spectrum",
    ]
    assert by.loc["Mir", "observations"] == 1
    assert by.loc["Mir", "slipped"] == 1
    assert by.loc["Mir", "mean_slip_days"] == 7.0
    assert by.loc["Mir", "max_slip_days"] == 7.0
    assert by.loc["Falcon 9 Block 5", "observations"] == 4
    assert by.loc["Falcon 9 Block 5", "slipped"] == 2
    assert by.loc["Falcon 9 Block 5", "share_slipped"] == 0.5
    assert by.loc["Falcon 9 Block 5", "mean_slip_days"] == 1.734
    assert by.loc["Falcon 9 Block 5", "max_slip_days"] == 5.942
    for rocket in ("Long March 12", "Long March 8A", "Soyuz 2.1b", "Spectrum"):
        assert by.loc[rocket, "observations"] == 2
        assert by.loc[rocket, "slipped"] == 0
        assert by.loc[rocket, "mean_slip_days"] == 0.0
