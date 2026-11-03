#!/usr/bin/env python3
"""List ISS rise / peak / set times over Spring, TX for the next 48 hours.

TLE source: CelesTrak (no account). Times printed in America/Chicago.
"""
from __future__ import annotations

from datetime import timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from skyfield.api import load, wgs84

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TLE_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle"
# Spring, Texas
LAT, LON = 30.08, -95.42
TZ = ZoneInfo("America/Chicago")


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    # Cache TLE under data/ so the project root stays clean
    tle_path = DATA / "stations.tle"
    if not tle_path.exists() or tle_path.stat().st_size == 0:
        import urllib.request
        urllib.request.urlretrieve(TLE_URL, tle_path)
    sats = load.tle_file(str(tle_path))
    by_name = {s.name: s for s in sats}
    if "ISS (ZARYA)" not in by_name:
        # Fallback: any name containing ISS
        iss = next((s for s in sats if "ISS" in s.name), None)
        if iss is None:
            print("ISS not found in TLE set")
            print("Available:", [s.name for s in sats[:10]])
            return 1
    else:
        iss = by_name["ISS (ZARYA)"]

    ts = load.timescale()
    home = wgs84.latlon(LAT, LON)
    t0 = ts.now()
    t1 = ts.tt_jd(t0.tt + 2)
    times, events = iss.find_events(home, t0, t1, altitude_degrees=10)
    labels = ["rise", "peak", "set"]
    print(f"ISS passes over Spring, TX ({LAT}, {LON}) — next 48h")
    print(f"Times in America/Chicago (CST/CDT as applicable)\n")
    for ti, e in zip(times, events):
        dt_utc = ti.utc_datetime().replace(tzinfo=timezone.utc)
        local = dt_utc.astimezone(TZ)
        label = labels[e] if e < len(labels) else str(e)
        print(f"{local.strftime('%Y-%m-%d %H:%M %Z')}  {label}")
    if len(times) == 0:
        print("(no passes above 10° altitude in the next 48 hours)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
