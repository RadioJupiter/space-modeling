#!/usr/bin/env python3
"""Fit log(a / M^(1/3)) vs log(P) for confirmed exoplanets; Kepler predicts slope 2/3.

Data: NASA Exoplanet Archive TAP (CSV). Query is properly URL-encoded.
"""
from __future__ import annotations

from urllib.parse import urlencode

import numpy as np
import pandas as pd
import requests

QUERY = (
    "select pl_name,pl_orbper,pl_orbsmax,st_mass "
    "from ps where default_flag=1 "
    "and pl_orbsmax is not null and st_mass is not null "
    "and pl_orbper is not null"
)
BASE = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"


def main() -> int:
    params = {"format": "csv", "query": QUERY}
    url = f"{BASE}?{urlencode(params)}"
    print("Fetching NASA Exoplanet Archive TAP…", flush=True)
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    # Archive sometimes prefixes comments with #
    from io import StringIO
    text = resp.text
    df = pd.read_csv(StringIO(text), comment="#")
    # Coerce numeric
    for col in ("pl_orbper", "pl_orbsmax", "st_mass"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["pl_orbper", "pl_orbsmax", "st_mass"])
    df = df[(df.pl_orbper > 0) & (df.pl_orbsmax > 0) & (df.st_mass > 0)]
    print(f"Planets used: {len(df)}")

    # Kepler III: a^3 / P^2 ~ M  =>  log(a / M^(1/3)) = (2/3) log(P) + c
    # Using P in years so solar system units are natural
    x = np.log10(df.pl_orbper / 365.25)
    y = np.log10(df.pl_orbsmax / df.st_mass ** (1 / 3))
    slope, intercept = np.polyfit(x, y, 1)
    print(f"fitted slope: {slope:.6f}  (Kepler predicts 0.666667)")
    print(f"intercept:    {intercept:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
