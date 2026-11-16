import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from slip_by_provider import provider_slip


def test_provider_slip():
    a = pd.DataFrame({"id": ["x", "y", "z"], "net": ["2026-11-01T00:00:00Z"] * 3})
    b = pd.DataFrame({
        "id": ["x", "y", "z"],
        "net": ["2026-11-03T00:00:00Z", "2026-11-01T00:00:00Z", "2026-11-09T00:00:00Z"],
        "status": ["Go", "Go", "Success"],  # z already flew -> excluded
        "name": ["A | p1", "A | p2", "B | p3"],
    })
    r = provider_slip([a, b]).set_index("provider")
    assert list(r.index) == ["A"]
    assert r.loc["A", "observations"] == 2 and r.loc["A", "slipped"] == 1
    assert r.loc["A", "mean_slip_days"] == 1.0 and r.loc["A", "max_slip_days"] == 2.0
