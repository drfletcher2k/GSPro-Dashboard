# Changelog

Reverse-chronological. Newest entry at the top.

## 2026-08-02 — Consolidated into `C:\ai\`

- **Copied** (not moved) from the nested repo
  `C:\Users\danfl\OneDrive\Stuff\gspro-dashboard-project\GSPro-Dashboard` to
  `C:\ai\gspro-dashboard`. The originals were left in place because the **"GSPro Dash Update"
  scheduled task is still enabled and targets that path**.
- Chose the inner nested copy over the outer one: it is the task's target and the only copy
  holding a commit not on origin (`f4cb119`). The outer copy had 0 unique commits.
- Uncommitted `index.html` regeneration committed to `wip/2026-08-02` and pushed. `f4cb119`
  reached origin as an ancestor of that branch. **Verified zero local-only commits remain.**
- **`main` deliberately left unmerged** — it is 1 ahead / 18 behind `origin/main`. Reconciling
  that is a non-trivial merge and a stop condition, and the unique commit was already safe.
- 🔴 **Established that the publishing pipeline is dead.** `origin/main`'s last genuine commit
  is `1363407`, 2026-07-26 08:47:50 — matching DR-12's note that the real pipeline ran from
  Kitchen's `C:\ClaudeCentral\GSPro_Dashboard` that morning. **That directory no longer exists.**
  Nothing has published since; the GitHub Pages dashboard is frozen at 26 July.
- Recorded that the scheduled task last ran 2026-07-23 with result `267014`
  (`SCHED_S_TASK_TERMINATED`) and is still `Ready` — able to fire from a copy 18 commits behind.
- Quarantined `C:\Users\danfl\OneDrive\Documents\Claude\Projects\GSPro Dashboard` (7 pipeline
  scripts, non-git, unreferenced) to `C:\ai\_quarantine\machineA\gspro-dashboard-Documents`.
- Added `docs/PROJECT.md`, this changelog, and `AGENTS.md` / `CLAUDE.md` / `GEMINI.md`.
- No pipeline code was modified and no scheduled task was changed.

## 2026-07-26 — Last genuine publish

- `1363407` Auto-update: 2026-07-26 08:47 (250 qualifying rounds), from the Kitchen copy that
  has since disappeared.

## 2026-05-04 — Stranded commit

- `f4cb119` Auto-update: 2026-05-04 10:38 (234 qualifying rounds), committed in the nested
  OneDrive copy and never pushed until 2026-08-02.
