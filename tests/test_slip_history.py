import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from slip_history import pair_stats


def test_pair_stats():
    a = pd.DataFrame({"id": ["x", "y"], "net": ["2026-11-01T00:00:00Z"] * 2})
    b = pd.DataFrame({"id": ["x", "y"], "net": ["2026-11-04T00:00:00Z", "2026-11-01T00:00:00Z"],
                      "status": ["Go", "Go"]})
    s = pair_stats(a, b)
    assert s["matched"] == 2 and s["slipped"] == 1 and s["max_slip_days"] == 3.0
