# GSPro Dashboard

Local analytics dashboard for GSPro portal round data, with automatic
detection of new qualifying rounds and live GitHub Pages deployment.

## Setup

1. Copy `.env.example` to `.env` and fill in your credentials:
   ```
   GSPRO_EMAIL=your@email.com
   GSPRO_PASSWORD=yourpassword
   ```

2. Install Python (3.8+). No third-party packages required — uses stdlib only.

## Usage

### Full update (fetch + filter + transform + regenerate dashboard)
```
python update.py
```

### Open dashboard locally
Open `index.html` in a browser after running `update.py`.

If charts don't load, serve locally:
```
python -m http.server 8080
```
Then open `http://localhost:8080/index.html`.

## Pipeline

```
fetch.py     → data/raw.json            (login + pull all players from GSPro Portal)
filter.py    → data/filtered.json       (complete 18-hole rounds, no Par 3 tees, players ≥5 rounds)
transform.py → data/transformed.json   (flat objects, all fields)
update.py    → data/latest.json         (deduped by player/round, solo rounds excluded)
             → data/last_updated.json   (ISO timestamp used by browser auto-refresh)
             → index.html               (regenerated)
```

## Auto-Update (Live Dashboard)

### How a qualifying session is detected

A **qualifying round** is any session that appears in the GSPro Portal API
(`/analytics/rounds/LoadData`) where:

- `holeCount` = 18
- The same `roundId` is shared by **2 or more distinct players** (multiplayer / head-to-head)
- No Par 3 tee designation

There is no local GSPro log file required. The portal API is the source of truth:
`fetch.py` authenticates and polls it directly. When the API returns a `(playerId, roundId)`
pair that is not already in `data/latest.json`, a new qualifying round has been posted
and the update pipeline fires.

### How the GitHub repo updates automatically

Run `poll_and_update.py` once and leave it in the background on the machine
that plays GSPro:

```
python poll_and_update.py
```

Every 5 minutes it:
1. Calls `fetch.py → filter.py → transform.py` to get the latest round list
2. Compares against `data/latest.json` to find genuinely new qualifying rounds
3. If new rounds exist: runs `update.py` (regenerates dashboard), then calls
   `auto_push.py` to commit and push `index.html`, `data/latest.json`, and
   `data/last_updated.json` to GitHub

**Optional environment variables:**

| Variable | Default | Description |
|---|---|---|
| `POLL_INTERVAL_MINUTES` | `5` | How often to check the API |
| `GIT_PUSH_BRANCH` | `main` | Branch to push updates to |
| `ONLY_WHILE_GSPRO_RUNS` | `0` | Set `1` to skip polls when GSPro.exe is not detected |

**PowerShell one-liner to start the poller minimised at login:**
```powershell
Start-Process python -ArgumentList "poll_and_update.py" -WorkingDirectory "C:\path\to\GSPro-Dashboard" -WindowStyle Minimized
```

Or add to Windows Task Scheduler: trigger = "At log on", action = `python poll_and_update.py`.

### How the GitHub Pages dashboard auto-refreshes

Every push to `main` that changes `index.html`, `data/latest.json`, or
`data/last_updated.json` triggers the GitHub Actions workflow
(`.github/workflows/pages.yml`), which deploys the updated page to GitHub Pages
within ~30 seconds.

The dashboard itself polls `data/last_updated.json` every 60 seconds. When the
`updated_at` timestamp is newer than the timestamp baked into the current page,
a banner appears and the browser reloads automatically — no manual refresh needed.

**One-time GitHub setup (do once):**
1. Go to **Settings → Pages** in the repository.
2. Set **Source** to `GitHub Actions`.
3. The workflow handles all subsequent deploys automatically.

## Validation

```
python validate.py
```

Checks: valid holeCount, no duplicate player/round pairs, flat objects, expected fields, size < 200 KB.

## Grafana / Home Assistant

See `GRAFANA_HA_SETUP.md` for data source setup, panel templates, and automation options.

## data/latest.json schema

Flat JSON array. Each round includes:

| Field | Type | Notes |
|---|---|---|
| roundId | str | GSPro round/session ID; may repeat across players in shared rounds |
| playerId | str | GSPro player UUID |
| player | str | Display name |
| date | str | YYYY-MM-DD |
| course | str | Course name |
| tee | str | Tee color |
| par | int | Course par |
| score | int | Gross strokes |
| net | int | Net strokes |
| courseHandicap | int | Playing handicap |
| holeCount | int | Always 18 |
| roundType | str | e.g. "Stroke Play" |
| ratingSlope | str | e.g. "72.1/131" |
| fairwaysHit | int | Count |
| fairwaysTarget | int | Eligible fairways |
| greensInReg | int | Count |
| greensTarget | int | Eligible GIR |
| putts | int | Passed through if present; not used by dashboard because autoputt is enabled |
| sandSaves | int | Sand save count |
| drivingDistLongest | float | Yards |
| eagles | int | |
| birdies | int | |
| pars | int | |
| bogeys | int | |
| doubleBogeys | int | |
| others | int | Triple+ |

Additional extractable fields available on the API but not included by default: `hiddenFromStatsTF`, `dateCreated`, `dateModified`. Add to `transform.py` if needed.

## data/last_updated.json schema

Small sentinel file written by `update.py` after each successful run.
The browser polls this to detect when new data has been deployed.

```json
{ "updated_at": "2026-05-03T18:00:00Z", "round_count": 234 }
```
