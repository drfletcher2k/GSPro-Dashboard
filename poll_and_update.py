"""
poll_and_update.py – Watches the GSPro Portal API for new qualifying rounds
(18-hole, multiplayer) and triggers a full dashboard update + GitHub push
whenever a new session is detected.

Run once and leave it running:
    python poll_and_update.py

Environment variables (optional):
    POLL_INTERVAL_MINUTES   How often to check (default: 5)
    GIT_PUSH_BRANCH         Branch to push to (default: main)
    ONLY_WHILE_GSPRO_RUNS   Set to "1" to skip polls when GSPro.exe is not running
"""
import json, os, sys, time, subprocess, datetime
from collections import defaultdict

DIR           = os.path.dirname(os.path.abspath(__file__))
LATEST        = os.path.join(DIR, "data", "latest.json")
TRANSFORMED   = os.path.join(DIR, "data", "transformed.json")
POLL_SEC      = int(os.environ.get("POLL_INTERVAL_MINUTES", "5")) * 60
ONLY_IF_OPEN  = os.environ.get("ONLY_WHILE_GSPRO_RUNS", "0") == "1"


def _ts():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _log(msg):
    print(f"[{_ts()}] {msg}", flush=True)


# ── helpers ───────────────────────────────────────────────────────────────────

def _gspro_running():
    """Return True if any GSPro* process is active (Windows only; always True elsewhere)."""
    if sys.platform != "win32":
        return True
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq GSPro*", "/NH"],
        capture_output=True, text=True
    )
    return "GSPro" in result.stdout


def _load_known_keys():
    """Return (playerId, roundId) pairs already in data/latest.json."""
    if not os.path.exists(LATEST):
        return set()
    with open(LATEST) as f:
        return {(r["playerId"], r["roundId"]) for r in json.load(f)}


def _fetch_qualifying_keys():
    """
    Pull fresh data from the GSPro Portal and return the set of
    (playerId, roundId) pairs that qualify: 18-hole AND multiplayer.

    Writes intermediate files (raw.json, filtered.json, transformed.json)
    which are .gitignore-d and are safe to overwrite on every poll.
    """
    import fetch as fetch_mod
    import filter as filter_mod
    import transform as transform_mod

    fetch_mod.run()
    filter_mod.run()
    transform_mod.run()

    with open(TRANSFORMED) as f:
        rounds = json.load(f)

    players_per_round = defaultdict(set)
    for r in rounds:
        rid = r.get("roundId")
        if rid:
            players_per_round[rid].add(r.get("playerId"))

    multiplayer_ids = {rid for rid, ps in players_per_round.items() if len(ps) >= 2}
    return {(r["playerId"], r["roundId"]) for r in rounds if r.get("roundId") in multiplayer_ids}


# ── core actions ──────────────────────────────────────────────────────────────

def _run_update():
    """Re-run the full pipeline: deduplicate, merge, regenerate dashboard."""
    result = subprocess.run(
        [sys.executable, os.path.join(DIR, "update.py")],
        capture_output=True, text=True
    )
    if result.stdout:
        for line in result.stdout.strip().splitlines():
            _log(f"  {line}")
    if result.returncode != 0:
        _log(f"  ERROR in update.py: {result.stderr.strip()}")
        return False
    return True


def _git_push():
    """Commit changed outputs and push to GitHub."""
    result = subprocess.run(
        [sys.executable, os.path.join(DIR, "auto_push.py")],
        capture_output=True, text=True
    )
    if result.stdout:
        for line in result.stdout.strip().splitlines():
            _log(f"  {line}")
    if result.returncode != 0:
        _log(f"  PUSH ERROR: {result.stderr.strip()}")


# ── poll loop ─────────────────────────────────────────────────────────────────

def _poll_once():
    if ONLY_IF_OPEN and not _gspro_running():
        _log("GSPro not running — skipping poll.")
        return

    _log("Checking GSPro Portal for new qualifying rounds…")
    try:
        known   = _load_known_keys()
        current = _fetch_qualifying_keys()
        new     = current - known

        if new:
            _log(f"  {len(new)} new qualifying round(s) detected — updating dashboard…")
            if _run_update():
                _git_push()
                _log("  Dashboard updated and pushed to GitHub.")
        else:
            _log(f"  No new rounds. ({len(current)} qualifying rounds on record)")
    except Exception as exc:
        _log(f"  Poll error: {exc}")


def main():
    _log(f"GSPro Dashboard poller started (every {POLL_SEC // 60} min"
         + (", only while GSPro is open" if ONLY_IF_OPEN else "") + ").")
    while True:
        _poll_once()
        time.sleep(POLL_SEC)


if __name__ == "__main__":
    main()
