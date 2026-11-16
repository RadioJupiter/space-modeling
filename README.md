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
| `launch_slip.py` | Snapshots upcoming launches to `data/upcoming_YYYY-MM-DD.csv` (including `window_start`, `window_end`, and `net_precision` on new snapshots); `--diff A B` compares two snapshots and reports slip days, with placeholder dates listed separately | Launch Library 2 |
| `slip_history.py` | Summarizes slip across every consecutive pair of snapshots; writes `data/slip_summary.csv` and `slip_summary.png`. Counts only timed comparisons | Local snapshots |
| `slip_by_provider.py` | Aggregates slip per rocket (parsed from launch name, since older list-mode snapshots omit provider); writes `data/slip_by_provider.csv`. Counts only timed comparisons | Local snapshots |
| `iss_passes.py` | ISS rise / peak / set over Spring, TX for the next 48 hours (America/Chicago) | [CelesTrak](https://celestrak.org) TLEs via Skyfield |
| `kepler_check.py` | Fits `log(a / M^(1/3))` vs `log(P)` for confirmed exoplanets; Kepler predicts slope ≈ 2/3 | [NASA Exoplanet Archive TAP](https://exoplanetarchive.ipac.caltech.edu) |

### Run

```bash
python src/launch_cadence.py      # a few LL2 pages; stay under the free rate limit
python src/launch_slip.py         # writes today's CSV under data/
python src/launch_slip.py --diff data/upcoming_2026-11-02.csv data/upcoming_2026-11-09.csv
python src/slip_history.py        # slip summary table + chart across all snapshots
python src/slip_by_provider.py    # per-rocket slip table
python -m pytest tests            # unit tests for the slip statistics and precision filter
python src/iss_passes.py
python src/kepler_check.py
```

Pass `--include-low-precision` to `launch_slip.py --diff` to also print placeholder and precision-change rows in the main listing (they are still labeled, and they are never mixed into the default summary tables).

## Rocket-shortage dataset (slip tracker)

`launch_slip.py` is meant to be run on a schedule (e.g. weekly). Each run freezes the public NET (no-earlier-than) date for every upcoming launch. Diffing two files measures how many days each launch slipped:

- **positive `slip_days`** → NET moved later (delay)
- **negative** → NET moved earlier
- launches that disappear between snapshots usually flew or were removed
- launches already flown (`Success` / `Failure` / `Partial Failure`) are dropped from the later snapshot

Over months this becomes your own delay dataset — useful for arguing about vehicle scarcity, pad congestion, or provider backlog without proprietary telemetry. Commit the CSVs (or store them as release artifacts) so the history is reproducible.

### Placeholder / precision filter

When Launch Library 2 only knows the day, month, quarter, or year of a launch, it publishes a placeholder NET such as `2026-11-30T00:00:00Z` ("sometime in November"). Swapping a placeholder for a real time — or a timed NET for a month-end date — can look like a multi-day "slip" that never happened.

Each NET is classed as `timed` (hour, minute, or second precision), `day`, or `coarse` (month or longer). A comparison only counts in the slip statistics when **both** NETs are timed. A *slip* is a timed NET moving later by at least 1 hour; smaller moves are T-0 refinements and are reported as minor adjustments. Precision changes and same-class placeholders are listed by `--diff` but excluded from `slip_summary.csv` and `slip_by_provider.csv`.

**Where precision comes from.** New snapshots (from this change onward) store LL2's own `net_precision` field, plus `window_start` and `window_end`, and use `mode=normal` so those fields are present. The three existing weekly snapshots (2026-11-02, 2026-11-09, 2026-11-16) were taken in list mode and do not have those columns, so a heuristic is used: a NET at exactly 00:00:00 UTC with a zero-length launch window (or no window recorded) is a placeholder (month-or-coarser if it falls on the last day of a month, otherwise day). The same heuristic, checked against the live `net_precision` field on 2026-11-16 in [Launch Delay Watch](https://github.com/RadioJupiter/launch-delay-watch), agreed on all 100 upcoming launches. A real launch scheduled at exactly 00:00:00 UTC with no window would be misread as a placeholder.

Reproduce the tables and chart from the committed snapshots:

```bash
python src/slip_history.py
python src/slip_by_provider.py
```

### Current figures (three weekly snapshots, 2026-11-02 to 2026-11-16)

Verified by running the commands above against the committed CSVs:

`data/slip_summary.csv` (mean / median / max are over the **timed** comparisons only):

| from | to | matched | timed | excluded | slipped | mean (d) | median (d) | max (d) |
|------|----|---------|-------|----------|---------|----------|------------|---------|
| 2026-11-02 | 2026-11-09 | 39 | 7 | 32 | 2 | 1.142 | 0.000 | 7.000 |
| 2026-11-09 | 2026-11-16 | 41 | 6 | 35 | 1 | 0.990 | 0.000 | 5.942 |

The three timed slips (≥ 1 hour later):

| Launch | Snapshot pair | NET move | slip (d) |
|--------|---------------|----------|----------|
| Mir \| Demo Flight | 2026-11-02 → 2026-11-09 | 2026-11-04 05:00Z → 2026-11-11 05:00Z | 7.000 |
| Falcon 9 Block 5 \| USSF-627 | 2026-11-02 → 2026-11-09 | 2026-11-09 03:17Z → 2026-11-10 03:07:15Z | 0.993 |
| Falcon 9 Block 5 \| USSF-317 | 2026-11-09 → 2026-11-16 | 2026-11-13 04:23Z → 2026-11-19 03:00Z | 5.942 |

`data/slip_by_provider.csv` (timed observations only):

| rocket | observations | slipped | share | mean (d) | max (d) |
|--------|--------------|---------|-------|----------|---------|
| Mir | 1 | 1 | 1.000 | 7.000 | 7.000 |
| Falcon 9 Block 5 | 4 | 2 | 0.500 | 1.734 | 5.942 |
| Long March 12 | 2 | 0 | 0.000 | 0.000 | 0.000 |
| Long March 8A | 2 | 0 | 0.000 | 0.000 | 0.000 |
| Soyuz 2.1b | 2 | 0 | 0.000 | 0.000 | 0.000 |
| Spectrum | 2 | 0 | 0.000 | 0.000 | 0.000 |

Before this filter, the 2026-11-09 → 2026-11-16 max was 18.792 days and Mir led the per-rocket table at mean 12.896 / max 18.792 (2 of 2 observations slipped). That 18.792-day move was Mir going from a timed NET (`2026-11-11T05:00:00Z`) to a month-end placeholder (`2026-11-30T00:00:00Z`) and is now excluded. The earlier timed Mir slip of 7.000 days remains. Other unfiltered artifacts: Vulcan VC6L +0.746 d and Electron +0.229 d (day placeholder gaining a clock time), and Starship −16.052 d (month placeholder replaced by a timed NET).

The sample is still small: 13 timed comparisons across two weekly pairs. Most upcoming rows in these snapshots are month- or year-end placeholders, which is why `matched` is much larger than `timed`.

## Notes

- Launch Library 2 free tier is rate-limited (~15 requests/hour). Cadence is capped at 4 pages; slip uses one call (`mode=normal`, limit=50).
- Space-Track.org is *not* used here (needs an account). Swap CelesTrak for Space-Track if you need the full catalog.
- Outputs are regenerated from live APIs; charts and CSVs in this tree are examples from the first run. Slip tables and `slip_summary.png` are regenerated from the committed weekly snapshots with the precision filter applied.

## License

MIT — data remains under each provider's terms.
