# Grafana & Home Assistant Setup

## data/latest.json format

A flat JSON array of rounds. Each object has these fields:
- roundId, playerId, player, date, course, tee, par, score (int), net, courseHandicap
- holeCount (always 18), roundType, ratingSlope
- fairwaysHit, fairwaysTarget, greensInReg, greensTarget
- sandSaves, drivingDistLongest
- eagles, birdies, pars, bogeys, doubleBogeys, others

The file is pre-filtered to complete 18-hole rounds only and excludes Par 3 tees/courses.

---

## Grafana

### Option A: JSON API (easiest)

1. Serve the file locally:
   ```
   cd "GSPro Dashboard"
   python3 -m http.server 8080
   ```
2. Install **JSON API** data source plugin:
   `grafana-cli plugins install simpod-json-datasource`
3. Add data source → URL: `http://localhost:8080/data/latest.json`
4. Create panels using field paths from the schema above.

### Option B: Infinity Plugin (no server needed)

1. Install: `grafana-cli plugins install yesoreyeram-infinity-datasource`
2. Add data source → Infinity
3. In a panel: Source = URL, Format = JSON, URL = `file:///absolute/path/to/data/latest.json`
4. Parse columns by name (date, score, player, holeCount, etc.)

### Useful Panel Types

| Metric | Visualization |
|---|---|
| Score trend per player | Time series (date on X, score on Y, filter by player) |
| Avg score leaderboard | Bar chart or Stat panel |
| Fairways/GIR % | Gauge or Bar gauge |
| Rounds per month | Bar chart grouped by player |
| Scoring distribution | Histogram |

### Recommended Transformations

- Data is already filtered to 18-hole rounds only
- Group by player + aggregate avg(score)
- Sort by date for time series

---

## Home Assistant

### Option A: REST sensor polling latest.json

Serve the file (see above) then add to `configuration.yaml`:

```yaml
sensor:
  - platform: rest
    resource: http://localhost:8080/data/latest.json
    name: gspro_rounds
    value_template: "{{ value_json | length }}"
    json_attributes_path: "$[0]"
    json_attributes:
      - player
      - date
      - course
      - score
      - holeCount
    scan_interval: 3600
```

Then use `sensor.gspro_rounds` attributes in Lovelace cards.

### Option B: File-based sensor (local only)

```yaml
sensor:
  - platform: command_line
    name: gspro_last_round
    command: >
      python3 -c "
      import json
      d = json.load(open('/path/to/data/latest.json'))
      r = sorted([x for x in d if x['player']=='Dan'], key=lambda x:x['date'])[-1]
      print(r['score'])
      "
    scan_interval: 3600
    unit_of_measurement: strokes
```

### Lovelace Example Card

```yaml
type: entities
title: GSPro - Last Round (Dan)
entities:
  - entity: sensor.gspro_last_round
    name: Score
```

---

## Automation: Run update after each session

### Windows Task Scheduler

Create a scheduled task:
- Program: `python`
- Arguments: `update.py`
- Start in: `C:\path\to\GSPro Dashboard`
- Trigger: Daily or on a schedule you choose

Or run manually after each session:
```bat
cd "C:\Users\danfl\OneDrive\Stuff\GSPro Dashboard"
python update.py
```

### Windows — watch for GSPro process exit (optional polling)

Save as `watch_gspro.bat` and run in background:
```bat
@echo off
:loop
tasklist /fi "imagename eq GSPro*" | find /i "GSPro" >nul
if %errorlevel% equ 0 (
    timeout /t 60 >nul
    goto loop
)
cd /d "C:\Users\danfl\OneDrive\Stuff\GSPro Dashboard"
python update.py
```

### macOS/Linux cron (if running on Mac/Linux)

```
# Run every hour
0 * * * * cd /path/to/GSPro\ Dashboard && python3 update.py >> /tmp/gspro_update.log 2>&1
```
