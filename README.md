# GSPro Dashboard

Local analytics dashboard for GSPro portal round data.

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

### Open dashboard
Open `index.html` in a browser after running `update.py`.

If charts don't load, serve locally:
```
python -m http.server 8080
```
Then open `http://localhost:8080/index.html`.

## Pipeline

```
fetch.py     → data/raw.json         (login + pull all players)
filter.py    → data/filtered.json    (complete 18-hole rounds, no Par 3 tees/courses, players ≥5 rounds)
transform.py → data/transformed.json (flat objects, all fields)
update.py    → data/latest.json      (deduped by player/round, final)
             → index.html            (regenerated)
```

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

## Auto-update

See `GRAFANA_HA_SETUP.md` → "Automation" section for Windows Task Scheduler and process-watch options.
