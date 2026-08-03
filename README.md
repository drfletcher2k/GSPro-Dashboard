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

Automation on top of that pipeline:

```
watcher.py     waits for a round-end signal, then calls runner.py   (leave running)
update_now.py  pushes an update on demand                           (the manual button)
runner.py      shared check → update.py → auto_push.py logic + locking
```

## Auto-Update (Live Dashboard)

### How a qualifying session is detected

A **qualifying round** is any session that appears in the GSPro Portal API
(`/analytics/rounds/LoadData`) where:

- `holeCount` = 18
- The same `roundId` is shared by **2 or more distinct players** (multiplayer / head-to-head)
- No Par 3 tee designation

The portal API is the source of truth for round *data*: `fetch.py` authenticates and
reads it. When the API returns a `(playerId, roundId)` pair that is not already in
`data/latest.json`, a new qualifying round has been posted and the update pipeline fires.

What the API cannot do is *tell you* a round finished — it is pull-only, with no
webhook or callback. So the portal is not checked on a timer; it is checked when the
sim PC produces a local signal that a round just ended (see below).

### How the GitHub repo updates automatically

Run `watcher.py` once and leave it in the background on the machine that plays GSPro:

```
python watcher.py
```

It sits idle until something says a round finished, then runs
`fetch.py → filter.py → transform.py`, compares against `data/latest.json`, and if
there are genuinely new rounds runs `update.py` and `auto_push.py` to commit and push
`index.html`, `data/latest.json`, and `data/last_updated.json`.

**Triggers, in order of usefulness:**

| Trigger | Reliability | Notes |
|---|---|---|
| Round-end line in GSPro's log | Best effort | GSPro's log wording is undocumented — see tuning below |
| GSPro exits | Reliable | Closing the suite always flushes the round to the portal |
| `Ctrl+Alt+G` hotkey | Manual | Global — works while GSPro is fullscreen |
| Safety-net check | Backstop | Every 60 min by default; set `SAFETY_NET_MINUTES=0` to disable |

Multiple signals for the same round are coalesced into one update. Because the portal
receives a round a few seconds *after* GSPro uploads it, a round-end signal that finds
nothing new is retried at 60s, 180s, and 300s before giving up.

**Tuning the round-end log trigger.** GSPro does not document what it writes when a
round ends, so the default pattern is a guess. To find the real line, run:

```
python watcher.py --tail
```

then finish a round and watch the output — lines matching the current pattern are
marked `>>`. Once you spot the actual round-end line, set `GSPRO_ROUND_END_PATTERN`
to a regex matching it. If no GSPro log is found at all, this trigger disables itself
and the other three still work.

**Optional environment variables:**

| Variable | Default | Description |
|---|---|---|
| `GSPRO_ROUND_END_PATTERN` | see `watcher.py` | Regex marking a finished round |
| `GSPRO_LOG_PATH` | auto-detected | Explicit path to the GSPro log to tail |
| `SAFETY_NET_MINUTES` | `60` | Backstop check interval; `0` disables |
| `POST_ROUND_DELAY_SEC` | `30` | Wait after a round-end signal before checking |
| `PROCESS_POLL_SEC` | `20` | How often to check whether GSPro is running |
| `HOTKEY_ENABLED` | `1` | Set `0` to skip registering `Ctrl+Alt+G` |
| `GIT_PUSH_BRANCH` | `main` | Branch to push updates to |

**PowerShell one-liner to start the watcher minimised at login:**
```powershell
Start-Process python -ArgumentList "watcher.py" -WorkingDirectory "C:\path\to\GSPro-Dashboard" -WindowStyle Minimized
```

Or add to Windows Task Scheduler: trigger = "At log on", action = `python watcher.py`.

### Pushing an update by hand

`Ctrl+Alt+G` while the watcher is running pushes an update immediately. If the watcher
is *not* running, double-click **`update_now.bat`** (or pin a shortcut to it on the
taskbar/desktop) — same effect, standalone:

```
python update_now.py
```

Both regenerate and push unconditionally rather than checking for new rounds first, so
the button always produces a fresh deploy. They share a lock file with `watcher.py`, so
it is safe to use one while the other is running.

> **Why not a button inside GSPro?** GSPro is a closed-source Unity application with no
> plugin or UI-extension API, so nothing here can add a button next to *Reset Launch
> Monitor* / *Exit Suite*. The global hotkey is the closest equivalent: it fires while
> GSPro is focused and fullscreen.

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
