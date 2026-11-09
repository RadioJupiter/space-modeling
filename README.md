# Space modeling snippets

Small, runnable Python scripts for launch cadence, schedule slip, ISS passes, and a Kepler-III check on real exoplanet data. Built as a portfolio / Git practice project for SyncHeart-adjacent space data work.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Scripts (`src/`)

| Script | What it does | Data source |
|--------|----------------|-------------|
| `launch_cadence.py` | Counts launches per quarter for the top rocket families; writes `cadence.png` | [Launch Library 2](https://thespacedevs.com/llapi) (free, ~15 calls/hour) |
| `launch_slip.py` | Snapshots upcoming launches to `data/upcoming_YYYY-MM-DD.csv`; `--diff A B` compares two snapshots and reports slip days | Launch Library 2 |
| `slip_history.py` | Summarizes slip across every consecutive pair of snapshots; writes `data/slip_summary.csv` and `slip_summary.png` | Local snapshots |
| `iss_passes.py` | ISS rise / peak / set over Spring, TX for the next 48 hours (America/Chicago) | [CelesTrak](https://celestrak.org) TLEs via Skyfield |
| `kepler_check.py` | Fits `log(a / M^(1/3))` vs `log(P)` for confirmed exoplanets; Kepler predicts slope ≈ 2/3 | [NASA Exoplanet Archive TAP](https://exoplanetarchive.ipac.caltech.edu) |

### Run

```bash
python src/launch_cadence.py      # a few LL2 pages; stay under the free rate limit
python src/launch_slip.py         # writes today's CSV under data/
python src/launch_slip.py --diff data/upcoming_2026-11-02.csv data/upcoming_2026-11-09.csv
python src/slip_history.py        # slip summary table + chart across all snapshots
python -m pytest tests            # unit test for the slip statistics
python src/iss_passes.py
python src/kepler_check.py
```

## Rocket-shortage dataset (slip tracker)

`launch_slip.py` is meant to be run on a schedule (e.g. weekly). Each run freezes the public NET (no-earlier-than) date for every upcoming launch. Diffing two files measures how many days each launch slipped:

- **positive `slip_days`** → NET moved later (delay)
- **negative** → NET moved earlier
- launches that disappear between snapshots usually flew or were removed

Over months this becomes your own delay dataset — useful for arguing about vehicle scarcity, pad congestion, or provider backlog without proprietary telemetry. Commit the CSVs (or store them as release artifacts) so the history is reproducible.

## Notes

- Launch Library 2 free tier is rate-limited (~15 requests/hour). Cadence is capped at 4 pages; slip uses one call.
- Space-Track.org is *not* used here (needs an account). Swap CelesTrak for Space-Track if you need the full catalog.
- Outputs are regenerated from live APIs; charts and CSVs in this tree are examples from the first run.

## License

MIT — data remains under each provider's terms.
