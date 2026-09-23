# AGENTS.md: gspro-dashboard

> Hub rules first: read `C:\AI-Hub\AGENTS.md`, then this file, then `docs/agent/STATUS.md`. (Codex and Gemini do not load the hub file automatically.)

## Project Context & Ownership
- Canonical path: `C:\AI-Hub\projects\gspro-dashboard` on `DESKTOP-V1STLIV`.
- Purpose: Local analytics dashboard for GSPro portal round data, auto-deployed to GitHub Pages.

## Critical Invariants
- Do not print or store secrets, tokens, or credential-bearing URLs in repo docs or logs.
- Preserve user data and live-service state unless the user approves a scoped change.

## Standard Build, Test, Lint, And Run Commands
- Run: `python update.py` (see `README.md`). Python 3.8+ stdlib only.

## Architecture Summary
- Pipeline: `update.py` -> `filter.py` -> `gen_dashboard.py`; `validate.py` checks output.
- Credentials live in `.env` (from `.env.example`); never print or commit them.
- Branch `kitchen-wip-2026-09-23` holds unmerged Kitchen WIP (MIN_ROUNDS 5->10, `data/manual_rounds.json`).

## Secondary Docs
- Historical logs, audits, and post-mortems: `docs/agent/HISTORY.md`.
