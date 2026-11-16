import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from slip_history import pair_stats


def test_pair_stats():
    # Use timed (non-midnight) NETs so the comparisons count.
    a = pd.DataFrame({"id": ["x", "y"], "net": ["2026-11-01T12:00:00Z"] * 2})
    b = pd.DataFrame({"id": ["x", "y"], "net": ["2026-11-04T12:00:00Z", "2026-11-01T12:00:00Z"],
                      "status": ["Go", "Go"]})
    s = pair_stats(a, b)
    assert s["matched"] == 2 and s["timed"] == 2 and s["excluded"] == 0
    assert s["slipped"] == 1 and s["max_slip_days"] == 3.0


def test_pair_stats_drops_flown():
    a = pd.DataFrame({"id": ["x", "y"], "net": ["2026-11-01T12:00:00Z"] * 2})
    b = pd.DataFrame({"id": ["x", "y"],
                      "net": ["2026-11-04T12:00:00Z", "2026-11-09T12:00:00Z"],
                      "status": ["Go", "Success"]})
    s = pair_stats(a, b)
    assert s["matched"] == 1 and s["slipped"] == 1 and s["max_slip_days"] == 3.0
