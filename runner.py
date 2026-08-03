"""
runner.py – Shared update logic used by watcher.py and update_now.py.

Checks the GSPro Portal for qualifying rounds that are not yet in
data/latest.json and, when new ones exist, regenerates the dashboard and
pushes it to GitHub.

A lock file keeps the watcher and a manual run from tripping over each other
on the git working tree.
"""
import contextlib
import datetime
import errno
import json
import os
import subprocess
import sys
import time
from collections import defaultdict

DIR         = os.path.dirname(os.path.abspath(__file__))
LATEST      = os.path.join(DIR, "data", "latest.json")
TRANSFORMED = os.path.join(DIR, "data", "transformed.json")
LOCK        = os.path.join(DIR, "data", ".update.lock")

# A run that somehow died without releasing the lock shouldn't wedge the
# watcher forever.
LOCK_STALE_SEC = 15 * 60


def _ts():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg):
    print(f"[{_ts()}] {msg}", flush=True)


# ── locking ───────────────────────────────────────────────────────────────────

@contextlib.contextmanager
def exclusive():
    """
    Yield True if this process took the update lock, False if another run
    already holds it.
    """
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)

    if os.path.exists(LOCK):
        try:
            age = time.time() - os.path.getmtime(LOCK)
            if age > LOCK_STALE_SEC:
                log(f"Clearing stale lock ({age / 60:.0f} min old).")
                os.remove(LOCK)
        except OSError:
            pass

    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise
        yield False
        return

    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield True
    finally:
        with contextlib.suppress(OSError):
            os.remove(LOCK)


# ── portal state ──────────────────────────────────────────────────────────────

def known_keys():
    """(playerId, roundId) pairs already recorded in data/latest.json."""
    if not os.path.exists(LATEST):
        return set()
    with open(LATEST) as f:
        return {(r["playerId"], r["roundId"]) for r in json.load(f)}


def fetch_qualifying_keys():
    """
    Pull fresh data from the GSPro Portal and return the (playerId, roundId)
    pairs that qualify: 18-hole AND multiplayer.

    Writes intermediate files (raw.json, filtered.json, transformed.json),
    which are .gitignore-d and safe to overwrite.
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


# ── actions ───────────────────────────────────────────────────────────────────

def _run_script(name):
    result = subprocess.run(
        [sys.executable, os.path.join(DIR, name)],
        cwd=DIR, capture_output=True, text=True
    )
    for line in (result.stdout or "").strip().splitlines():
        if line:
            log(f"  {line}")
    if result.returncode != 0:
        log(f"  ERROR in {name}: {(result.stderr or '').strip()}")
        return False
    return True


def run_update():
    """Re-run the full pipeline: deduplicate, merge, regenerate dashboard."""
    return _run_script("update.py")


def git_push():
    """Commit changed outputs and push to GitHub."""
    return _run_script("auto_push.py")


# ── entry point ───────────────────────────────────────────────────────────────

def check_and_update(reason, force=False):
    """
    Run one update cycle.

    force=True skips the "is there anything new?" check and regenerates and
    pushes unconditionally — that's what the manual trigger does, so pressing
    the button always produces a fresh deploy.

    Returns one of: "pushed", "no-new", "busy", "error".
    """
    with exclusive() as acquired:
        if not acquired:
            log(f"Trigger ({reason}) ignored — an update is already running.")
            return "busy"

        log(f"Trigger: {reason}")
        try:
            if not force:
                new = fetch_qualifying_keys() - known_keys()
                if not new:
                    log("  No new qualifying rounds.")
                    return "no-new"
                log(f"  {len(new)} new qualifying round(s) — updating dashboard…")

            if not run_update():
                return "error"
            if not git_push():
                return "error"

            log("  Dashboard updated and pushed to GitHub.")
            return "pushed"
        except Exception as exc:
            log(f"  Update error: {exc}")
            return "error"
