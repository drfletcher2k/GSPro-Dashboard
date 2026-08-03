"""
update_now.py – Push a dashboard update right now.

This is the manual "button": regenerate the dashboard from the current portal
data and push it to GitHub, without waiting for a trigger. Safe to run while
watcher.py is running — they share a lock.

    python update_now.py
"""
import sys

import runner

if __name__ == "__main__":
    result = runner.check_and_update("manual run", force=True)
    sys.exit(0 if result in ("pushed", "no-new") else 1)
