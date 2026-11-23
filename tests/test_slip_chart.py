import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from slip_by_provider import plot_provider_slip


def test_plot_writes_png(tmp_path):
    df = pd.DataFrame({"provider": ["A", "B"], "observations": [3, 2], "mean_slip_days": [1.0, 2.5]})
    out = tmp_path / "c.png"
    assert plot_provider_slip(df, out)
    assert out.stat().st_size > 0


def test_plot_skips_when_too_few(tmp_path):
    df = pd.DataFrame({"provider": ["A"], "observations": [1], "mean_slip_days": [1.0]})
    assert not plot_provider_slip(df, tmp_path / "c.png")
