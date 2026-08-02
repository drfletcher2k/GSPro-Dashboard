# gspro-dashboard

## Purpose

A golf statistics dashboard for **GSPro** (golf simulator software). A Python pipeline polls
round data, filters and transforms it, regenerates a static `index.html`, commits the result,
and publishes it via GitHub Pages.

Features visible in the history include a "Hall of Fame" of the four lowest rounds all-time and
a "What qualifies?" explainer, with auto-update commits tracking a qualifying-round count
(250 as of the last real update).

## Stack + versions

Python producing static HTML, published by GitHub Pages.

- `poll_and_update.py` — the scheduled entrypoint
- `fetch.py` / `filter.py` / `transform.py` / `gen_dashboard.py` / `update.py` — pipeline stages
  (present in the older non-git copy; the tracked copy is the consolidated version)
- `index.html` — the generated dashboard
- No package manifest or lockfile

## Entrypoint and run command

```bash
python poll_and_update.py
```

This is what the Windows scheduled task **"GSPro Dash Update"** invokes.

## Directory map

```
.
├── poll_and_update.py     # scheduled entrypoint
├── index.html             # generated dashboard
├── data/                  # raw.json / filtered.json / transformed.json all GITIGNORED
├── docs/
└── .gitignore             # .env, .cookies, data/*.json, __pycache__/
```

123 files.

## External dependencies and services

- **GSPro** — the source of round data.
- **GitHub Pages** — two active workflows, `Deploy to GitHub Pages` and
  `pages-build-deployment`. The repository is **public**, which Pages requires.
- `.env` and `.cookies` are gitignored; **neither exists on disk** in this copy, and no
  credential-shaped files were found.

## 🔴 The publishing pipeline appears to have died on 2026-07-26

`origin/main`'s last genuine commit is **`1363407`, 2026-07-26 08:47:50** —
*"Auto-update: 2026-07-26 08:47 (250 qualifying rounds)"*.

That timestamp matches DR-12's July note that GSPro's "real data pipeline ran this morning,
08:11–08:47 AM" from Kitchen's `C:\ClaudeCentral\GSPro_Dashboard`. **That Kitchen directory no
longer exists** — the 2026-08-01 audit could not find it, and neither could this migration.

So the machine that was actually publishing this dashboard is gone, and nothing has updated
`origin/main` since. The dashboard on GitHub Pages is frozen at 26 July.

Note also that origin's commits are authored by **`drf1980@gmail.com`**, a different address
from the one used elsewhere in this consolidation.

## ⚠️ Three copies, a nested repo, and a scheduled task pointing at the wrong one

Before consolidation:

| Copy | Git | State |
|---|---|---|
| `OneDrive\Stuff\gspro-dashboard-project` (outer) | yes, same remote | HEAD `1959065` (2026-05-03), 3 dirty, **0 unique commits** |
| `…\gspro-dashboard-project\GSPro-Dashboard` (**nested inside the outer**) | yes, same remote | HEAD `f4cb119` (2026-05-04), 1 dirty, **1 unique commit** |
| `OneDrive\Documents\Claude\Projects\GSPro Dashboard` | no | 7 pipeline scripts, older |

A git repository nested inside another git repository on the **same remote** — the outer repo
sees `GSPro-Dashboard/` as an untracked directory.

**The live scheduled task "GSPro Dash Update" targets the inner copy**, which is 18 commits
behind `origin/main`. Its last run was **2026-07-23 14:15:34** with result `267014`
(`SCHED_S_TASK_TERMINATED` — the run was terminated). The task is still in `Ready` state, so it
can fire again, from a stale copy.

A second task, **"GSPro Open Ready Watcher"**, is `Disabled` and points into
`C:\Users\danfl\.claude\projects\ai-ops-home\windows\gspro\` — a Claude session-cache path.

## Current state

This copy was taken from the **inner** repo (the task's target, and the only one with unique
work). `main` here is **1 ahead / 18 behind** `origin/main` — genuinely diverged, not merely
stale.

The one unique commit, `f4cb119`, **is safe on origin** — it went up as an ancestor of the
pushed `wip/2026-08-02` branch. Verified: zero local-only commits remain.

`main` was **not** merged or rebased onto origin. Reconciling an 18-commit divergence is a
non-trivial merge, which is a stop condition, and the safe content was already preserved.

## Known issues

- **The publishing pipeline is dead** since 2026-07-26 — see above. The Pages site is stale.
- **The scheduled task points at a copy 18 commits behind origin.** If it fires and pushes, it
  would publish regressed content.
- **The nested-repo layout is still in place** in OneDrive and was not untangled — the outer
  repo and inner repo share a remote, which no tooling handles gracefully.
- **Git repositories inside OneDrive.** These copies live in a cloud-synced folder, which is
  exactly the corruption risk the consolidation policy exists to avoid.
- **`main` is diverged and unmergeable without a decision** — 1 ahead, 18 behind.
- **Commits authored under a different email** (`drf1980@gmail.com`) than the rest of this work.

## Unknown — needs owner input

- **Whether this project should still run at all**, given the machine that published it is gone.
- **Where the pipeline should live now.** The Kitchen copy that did the real work no longer
  exists; only stale OneDrive copies and origin remain.
- **Whether to disable or repoint "GSPro Dash Update"** before it fires against stale state.
- **How to reconcile `main`** — most likely reset to `origin/main` and discard the local
  divergence, since `f4cb119` is already preserved. That is a destructive-ish call and was left
  to you.

## Decision log

| Date | Decision |
|---|---|
| 2026-05-04 | `f4cb119` auto-update committed in the nested OneDrive copy. Never pushed until 2026-08-02. |
| 2026-07-23 | Last run of the "GSPro Dash Update" task — terminated (`267014`). |
| 2026-07-26 | Prior effort (DR-12) committed Kitchen's `GSPro_Dashboard` state as `b3bc9f9` and did not push. It judged Kitchen live and OneDrive ~3 months stale. Origin's last genuine commit is from this morning. |
| 2026-08-02 | The Kitchen copy that DR-12 called authoritative **could not be found** — confirming the audit's finding that `C:\ClaudeCentral\GSPro_Dashboard` no longer exists. |
| 2026-08-02 | The **inner** nested copy promoted — it is the scheduled task's target and the only copy with a unique commit. **Copied, not moved**, because the task is still enabled and points at it. |
| 2026-08-02 | Uncommitted `index.html` regeneration committed to `wip/2026-08-02` and pushed. `f4cb119` reached origin as an ancestor of that branch. |
| 2026-08-02 | **`main` deliberately not merged or rebased.** 1 ahead / 18 behind is a non-trivial reconciliation and a stop condition; the unique content was already safe. |
| 2026-08-02 | The non-git `Documents\Claude\Projects\GSPro Dashboard` copy quarantined — older pipeline scripts, no git, not referenced by any task. |
