# AGENTS.md: gspro-dashboard

> **CRITICAL INSTRUCTION FOR ALL AI AGENTS**: Read this file completely before inspecting or modifying code in this directory. Before completing your session, you MUST run existing tests and record your changes in the Session Log at the bottom.

**Location**: `C:\ai-shared\gspro-dashboard` — dual-cloned on both KITCHEN (`DESKTOP-1O08HKV`) and OFFICE PCs. A pre-push hook fetches and blocks the push if this branch is behind its remote-tracking branch (pull first). Currently checked out on `wip/2026-08-02`, not `main` — see §4 for the `main`/`origin/main` divergence.

## 1. Project Identity & Purpose
- **Core Stack**: Python 3.8+ (stdlib only — `urllib`, `json`, `http.cookiejar`; no third-party packages) for the data pipeline; static HTML/vanilla JS + Chart.js 4.4.0 (via CDN) for the dashboard frontend.
- **Primary Objective**: Scrapes round/score data for a group of golfers from the GSPro Portal web app, filters it down to qualifying 18-hole multiplayer rounds, and regenerates a static analytics dashboard (`index.html`) that auto-publishes to GitHub Pages.
- **Entry Points**:
  - `update.py` — full pipeline (fetch → filter → transform → dedupe/merge → regenerate `index.html` → write sentinel file). Run manually after a session.
  - `poll_and_update.py` — long-running watcher; polls the GSPro Portal API every N minutes, and on new qualifying rounds runs `update.py` then `auto_push.py`.
  - `gen_dashboard.py` — regenerates `index.html` from `data/latest.json` only (called by `update.py`, can be run standalone).
  - `validate.py` — sanity-checks `data/latest.json` (schema, dupes, size).
  - `auto_push.py` — git add/commit/push of the three tracked output files, called by the poller.

## 2. Architecture & Dependencies
- **Internal Modules**:
  - `fetch.py` — logs into `portal.gsprogolf.com` and pulls raw round/score data per player → `data/raw.json`.
  - `filter.py` — keeps only complete 18-hole, non-Par-3 rounds for players with ≥5 qualifying rounds → `data/filtered.json`.
  - `transform.py` — flattens the nested API shape into flat round objects → `data/transformed.json`.
  - `update.py` — dedupes by (playerId, roundId), drops solo (single-player) rounds, writes `data/latest.json` + `data/last_updated.json`, regenerates `index.html`.
  - `gen_dashboard.py` — reads `data/latest.json` and builds the self-contained `index.html` (embeds Chart.js via CDN, per-player colors, stats).
  - `auto_push.py` — stages only `data/latest.json`, `data/last_updated.json`, `index.html`; commits; pushes with retry/backoff to `$GIT_PUSH_BRANCH` (default `main`).
  - `auto-push.bat` — a separate, older push script; hardcodes a stale path (`C:\Users\danfl\OneDrive\Stuff\gspro-dashboard-project`) that does not match this repo's current location, and uses `git push -f origin main` (force push). Likely dead/legacy — do not rely on it without fixing the path and removing `-f`.
  - `watch_gspro_update.ps1` — Windows watcher that runs `update.py` after the GSPro process exits; also hardcodes a stale path (`C:\Users\danfl\OneDrive\Stuff\GSPro Dashboard`).
  - `.github/workflows/pages.yml` — GitHub Actions workflow; on push to `main` touching `index.html`/`data/latest.json`/`data/last_updated.json`, deploys the repo root to GitHub Pages.
  - `data/` — pipeline output; only `data/latest.json` is committed/tracked at rest, intermediate files (`raw.json`, `filtered.json`, `transformed.json`) are `.gitignore`-d.
- **Key External APIs / Services**: GSPro Portal (`https://portal.gsprogolf.com`, `/analytics/rounds/LoadData`) — undocumented/unofficial HTML+JSON endpoints scraped via cookie-based login; GitHub Pages (static hosting); GitHub Actions (`actions/configure-pages`, `actions/upload-pages-artifact`, `actions/deploy-pages`).
- **Environment Variables Required**: `GSPRO_EMAIL`, `GSPRO_PASSWORD` (or a `.env` file, key=value format, read manually by `fetch.py`'s `_env()` — not python-dotenv). Optional for the poller: `POLL_INTERVAL_MINUTES` (default 5), `GIT_PUSH_BRANCH` (default `main`), `ONLY_WHILE_GSPRO_RUNS` (default `0`).

## 3. Build, Test, & Execution Commands

```bash
# Install dependencies
# None — stdlib only. No requirements.txt / pyproject.toml exists in this repo.

# Run local dev/test server (view dashboard locally after running update.py)
python -m http.server 8080
# then open http://localhost:8080/index.html

# Execute test suite
python validate.py
# (there is no unit-test suite; validate.py is the closest equivalent —
#  checks data/latest.json schema, duplicate keys, size < 200KB)

```

## 4. Current State & Known Technical Debt
 * **Status**: Broken (publishing pipeline) / Functional (local pipeline and dashboard generation still work)
 * **Known Technical Debt / Bugs**:
   * [ ] **Publishing pipeline is broken since 2026-07-26.** `origin/main`'s last genuine commit is `1363407` (2026-07-26 08:47), which came from a Kitchen directory `C:\ClaudeCentral\GSPro_Dashboard` that **no longer exists**. The GitHub Pages dashboard has been frozen at that date ever since. Local `main` is diverged (1 ahead / 18 behind `origin/main`) and was deliberately NOT merged — the one unique local commit is preserved on branch `wip/2026-08-02` instead. Decide on a new publish path/source directory before expecting GitHub Pages to update again.
   * [ ] `auto-push.bat` hardcodes a stale working directory (`C:\Users\danfl\OneDrive\Stuff\gspro-dashboard-project`) and force-pushes (`git push -f origin main`) — inconsistent with and riskier than `auto_push.py`. Likely dead legacy script.
   * [ ] `watch_gspro_update.ps1` hardcodes a stale working directory (`C:\Users\danfl\OneDrive\Stuff\GSPro Dashboard`).
   * [ ] No dependency manifest exists (relies on stdlib only by design, per README — flagging so agents don't assume a missing `requirements.txt` is an oversight).
   * [ ] No automated test suite; `validate.py` only checks output data shape, not pipeline logic.
   * [ ] `fetch.py`'s GSPro Portal login/scrape logic depends on undocumented HTML structure (regex-scraped CSRF token and `<option>` tags) — fragile to upstream site changes.
 * **Key Constraints**: Keep `data/latest.json` under 200KB (enforced by `validate.py`); dashboard must remain a single self-contained `index.html` (no build step, no bundler); do not commit `.env` or `.cookies` (already gitignored); only `data/latest.json`, `data/last_updated.json`, and `index.html` should be pushed by automated tooling.
## 6. Security & Runtime Audit (2026-08-02)
 * **Credential/history sweep**: `git log --all --diff-filter=A --name-only` (all branches, full history) piped through a case-insensitive filter for `.env|secret|credential|password|token|key` returned **zero hits** — no file matching those patterns has ever been added in any commit on any branch. Combined with the earlier working-tree sweep (also zero hits), no evidence of a committed or historical credential leak was found in this repo.
 * **Gitignored-but-present check**: `git status --ignored=matching --porcelain` shows only `?? AGENTS.md` (this file, untracked/new). None of the `.gitignore`-listed paths (`.env`, `.cookies`, `data/raw.json`, `data/filtered.json`, `data/transformed.json`) are present on disk — nothing to flag for size or accidental tracking risk.
 * **Scheduled task "GSPro Dash Update" — root cause identified, partially fixed 2026-08-02**: `Get-ScheduledTaskInfo` confirmed `LastRunTime = 11/30/1999` (sentinel for "never run") and `LastTaskResult = 267011` (`SCHED_S_TASK_HAS_NOT_RUN`). Root cause: the task's only trigger was an `MSFT_TaskLogonTrigger`, which fires only on a *future* interactive logon — it does not retroactively fire for an already-active session, and `danfl`'s session predates the task's creation with no intervening logoff/logon.
   Confirmed this is the *correct* trigger type for the intent, not a wrong choice: `poll_and_update.py`'s own docstring says "Run once and leave it running" — it's meant to be started once per session and left as a long-lived poller (default 5-minute interval, internal loop), not re-invoked repeatedly by Task Scheduler. So `AtLogOn` is right for future logins; the task just needed (a) a manual kick for the *current* session, and (b) an execution model that doesn't kill a process meant to run indefinitely.
   **What was fixed**: manually started the task now via `Start-ScheduledTask` — confirmed a live `python.exe poll_and_update.py` process is running (PID 13504 at time of fix). **What could NOT be fixed (blocked by lack of admin rights in this session)**: `Set-ScheduledTask` failed with "Access is denied" when attempting to (1) add an `AtStartup` trigger as a reboot fallback, and (2) fix `Settings.ExecutionTimeLimit` — currently `PT72H` (72 hours), which will silently kill this "leave it running" watcher after 3 days even though it started successfully; also `RestartCount = 0`, so it won't restart itself if it crashes before that. Old task definition backed up to `C:\ai-shared\_task-backups\GSPro-Dash-Update-before-trigger-fix-2026-08-02.xml` before any attempt.
   **To finish this, run the following from an elevated PowerShell**:
   ```powershell
   $logonTrigger = New-ScheduledTaskTrigger -AtLogOn
   $startupTrigger = New-ScheduledTaskTrigger -AtStartup
   $newSettings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Seconds 0) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5)
   $newSettings.DisallowStartIfOnBatteries = $false
   $newSettings.StopIfGoingOnBatteries = $false
   Set-ScheduledTask -TaskName "GSPro Dash Update" -Trigger @($logonTrigger, $startupTrigger) -Settings $newSettings
   ```

## 7. Session Log (Mandatory Agent Updates)
*Format: [YYYY-MM-DD] [Agent Name/Model] - Summary of changes made*
 * [2026-08-02] [Setup-Agent] - Migrated legacy benchmark/context docs to consolidated AGENTS.md format.
 * [2026-08-02] [Audit-Agent] - Ran git-history credential sweep (no hits), diagnosed never-run "GSPro Dash Update" scheduled task (logon trigger never fired since registration), confirmed no gitignored artifacts present on disk. Added Section 6 (Security & Runtime Audit).
 * [2026-08-02] [Claude Sonnet 5, follow-up session] - Confirmed `poll_and_update.py` is meant to be a persistent per-session watcher (not a repeating batch job), validating the logon-trigger diagnosis. Manually started the task for the current session (verified running, PID 13504). Attempted to add an `AtStartup` trigger and fix `ExecutionTimeLimit`/`RestartCount` via `Set-ScheduledTask` — blocked by "Access is denied" (non-elevated session). Backed up the task definition and left exact elevated PowerShell in §6 for the user to complete the fix.
