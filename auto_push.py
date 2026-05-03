"""
auto_push.py – Stage changed dashboard outputs, commit with a timestamp, and
push to GitHub.  Called by poll_and_update.py after a successful pipeline run.

Usage (standalone):
    python auto_push.py

Environment variables (optional):
    GIT_PUSH_BRANCH   Branch to push to (default: main)
"""
import os, sys, subprocess, datetime

DIR    = os.path.dirname(os.path.abspath(__file__))
BRANCH = os.environ.get("GIT_PUSH_BRANCH", "main")

# Files that change on every update — push only these; never push .env, .cookies, etc.
TRACKED = [
    "data/latest.json",
    "data/last_updated.json",
    "index.html",
]


def _run(cmd, **kwargs):
    return subprocess.run(cmd, cwd=DIR, capture_output=True, text=True, **kwargs)


def main():
    ts      = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    msg     = f"Auto-update: {ts}"

    # Count qualifying rounds for the commit message
    try:
        import json
        with open(os.path.join(DIR, "data", "latest.json")) as f:
            count = len(json.load(f))
        msg += f" ({count} qualifying rounds)"
    except Exception:
        pass

    # Stage only the tracked output files that exist
    existing = [p for p in TRACKED if os.path.exists(os.path.join(DIR, p))]
    if not existing:
        print("Nothing to stage — skipping push.")
        return

    r = _run(["git", "add"] + existing)
    if r.returncode != 0:
        print(f"git add failed: {r.stderr.strip()}")
        sys.exit(1)

    # Commit (skip if nothing actually changed)
    r = _run(["git", "commit", "-m", msg])
    if r.returncode != 0:
        if "nothing to commit" in r.stdout + r.stderr:
            print("No changes — nothing to push.")
            return
        print(f"git commit failed: {r.stderr.strip()}")
        sys.exit(1)
    print(r.stdout.strip())

    # Push with retry (up to 4 attempts, exponential back-off)
    delay = 2
    for attempt in range(1, 5):
        r = _run(["git", "push", "-u", "origin", BRANCH])
        if r.returncode == 0:
            print(f"Pushed to origin/{BRANCH}")
            return
        print(f"Push attempt {attempt} failed: {r.stderr.strip()}")
        if attempt < 4:
            import time
            time.sleep(delay)
            delay *= 2

    print("All push attempts failed.")
    sys.exit(1)


if __name__ == "__main__":
    main()
