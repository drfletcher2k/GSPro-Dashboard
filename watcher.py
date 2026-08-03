"""
watcher.py – Event-driven dashboard updates. Replaces the old 5-minute poller.

Instead of hitting the GSPro Portal on a timer, this waits for a local signal
that a round actually finished and only then checks the portal and pushes.

Run once and leave it running on the machine that plays GSPro:

    python watcher.py

Triggers
--------
1. Round-end log line   GSPro's Unity log is tailed for a round-completion
                        line. Best effort — GSPro's wording is not documented,
                        so the pattern is configurable. Use `--tail` to see
                        what your install actually writes.
2. GSPro exits          Closing the suite always flushes the round to the
                        portal, so this one is reliable on its own.
3. Hotkey (Ctrl+Alt+G)  Windows-only global hotkey; works while GSPro is
                        fullscreen. This is the manual "push now" button.
4. Safety net           A slow backstop check (default: every 60 minutes,
                        set to 0 to disable) in case every signal above is
                        missed.

Environment variables (all optional)
------------------------------------
    GSPRO_LOG_PATH              Explicit path to the GSPro log to tail
    GSPRO_ROUND_END_PATTERN     Regex marking a finished round
    SAFETY_NET_MINUTES          Backstop interval, 0 disables (default: 60)
    POST_ROUND_DELAY_SEC        Wait before the first check (default: 30)
    PROCESS_POLL_SEC            GSPro process check interval (default: 20)
    HOTKEY_ENABLED              "0" to disable the global hotkey
    GIT_PUSH_BRANCH             Branch to push to (default: main)
"""
import contextlib
import os
import queue
import re
import subprocess
import sys
import threading
import time

import runner
from runner import log

DIR = os.path.dirname(os.path.abspath(__file__))

ROUND_END_PATTERN = re.compile(os.environ.get(
    "GSPRO_ROUND_END_PATTERN",
    r"(?i)round\s*(complete|completed|finished|ended)"
    r"|scorecard\s*(saved|posted|uploaded|submitted)"
    r"|(post|upload)(ing|ed)?\s+round"
))

SAFETY_NET_SEC       = int(os.environ.get("SAFETY_NET_MINUTES", "60")) * 60
POST_ROUND_DELAY_SEC = int(os.environ.get("POST_ROUND_DELAY_SEC", "30"))
PROCESS_POLL_SEC     = int(os.environ.get("PROCESS_POLL_SEC", "20"))
HOTKEY_ENABLED       = os.environ.get("HOTKEY_ENABLED", "1") != "0"

# The portal receives a finished round a few seconds after GSPro uploads it,
# and "a few" is not guaranteed. If a round-end signal fires but the portal
# has nothing new yet, re-check on this schedule before giving up.
ROUND_END_RETRY_SEC = [60, 180, 300]

events = queue.Queue()


# ── trigger: GSPro log tail ───────────────────────────────────────────────────

def find_gspro_log():
    """
    Locate GSPro's log file. Unity writes to
    %USERPROFILE%\\AppData\\LocalLow\\<Company>\\<Product>\\Player.log, and
    GSPro also keeps logs under its install directory.
    """
    explicit = os.environ.get("GSPRO_LOG_PATH")
    if explicit:
        return explicit if os.path.exists(explicit) else None

    candidates = []
    lowlow = os.path.join(os.path.expanduser("~"), "AppData", "LocalLow")
    if os.path.isdir(lowlow):
        for company in os.listdir(lowlow):
            if "gspro" not in company.lower():
                continue
            company_dir = os.path.join(lowlow, company)
            for root, _dirs, files in os.walk(company_dir):
                for name in files:
                    if name.lower().endswith(".log"):
                        candidates.append(os.path.join(root, name))

    for base in (r"C:\GSPro", os.path.join(os.environ.get("PROGRAMFILES", ""), "GSPro")):
        if base and os.path.isdir(base):
            for root, _dirs, files in os.walk(base):
                if "log" not in os.path.basename(root).lower():
                    continue
                for name in files:
                    if name.lower().endswith(".log"):
                        candidates.append(os.path.join(root, name))

    if not candidates:
        return None
    return max(candidates, key=lambda p: os.path.getmtime(p))


def _tail_lines(path, on_line, stop):
    """Follow `path`, calling on_line() for each appended line."""
    handle = None
    inode = None
    pos = 0
    first_open = True

    while not stop.is_set():
        try:
            if handle is None:
                if not os.path.exists(path):
                    time.sleep(2)
                    continue
                handle = open(path, "r", encoding="utf-8", errors="replace")
                if first_open:
                    # Existing history is not new activity — start at the end.
                    handle.seek(0, os.SEEK_END)
                    first_open = False
                # After a rotation or truncation the whole new file *is* new
                # activity, so read it from the start.
                pos = handle.tell()
                inode = os.stat(path).st_ino

            line = handle.readline()
            if line:
                pos = handle.tell()
                on_line(line.rstrip("\n"))
                continue

            # No new data — check for rotation or truncation before sleeping.
            try:
                st = os.stat(path)
                # st_ino is 0 on filesystems that don't report it; fall back to
                # detecting the file shrinking.
                rotated = inode and st.st_ino and st.st_ino != inode
                if rotated or st.st_size < pos:
                    handle.close()
                    handle = None
                    continue
            except OSError:
                handle.close()
                handle = None
                continue

            time.sleep(1)
        except Exception as exc:
            log(f"Log tail error: {exc}")
            if handle:
                with contextlib.suppress(Exception):
                    handle.close()
            handle = None
            time.sleep(5)

    if handle:
        handle.close()


def log_trigger(stop):
    path = find_gspro_log()
    if not path:
        log("No GSPro log found — round-end log trigger disabled. "
            "Set GSPRO_LOG_PATH to enable it. "
            "(GSPro-exit and hotkey triggers are unaffected.)")
        return

    log(f"Tailing GSPro log: {path}")

    def on_line(line):
        if ROUND_END_PATTERN.search(line):
            log(f"Round-end line matched: {line.strip()[:160]}")
            events.put(("round finished (log)", POST_ROUND_DELAY_SEC, len(ROUND_END_RETRY_SEC)))

    _tail_lines(path, on_line, stop)


# ── trigger: GSPro process exit ───────────────────────────────────────────────

def gspro_running():
    if sys.platform != "win32":
        return False
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq GSPro*", "/NH"],
        capture_output=True, text=True
    )
    return "GSPro" in result.stdout


def process_trigger(stop):
    if sys.platform != "win32":
        log("Not Windows — GSPro process trigger disabled.")
        return

    was_running = gspro_running()
    if was_running:
        log("GSPro is running.")

    while not stop.is_set():
        stop.wait(PROCESS_POLL_SEC)
        if stop.is_set():
            break
        try:
            now_running = gspro_running()
        except Exception as exc:
            log(f"Process check error: {exc}")
            continue

        if now_running and not was_running:
            log("GSPro started.")
        elif was_running and not now_running:
            events.put(("GSPro closed", POST_ROUND_DELAY_SEC, len(ROUND_END_RETRY_SEC)))
        was_running = now_running


# ── trigger: global hotkey (the manual button) ────────────────────────────────

def hotkey_trigger(stop):
    """
    Register Ctrl+Alt+G system-wide so it fires even with GSPro focused.
    Windows-only; a no-op elsewhere.
    """
    if sys.platform != "win32" or not HOTKEY_ENABLED:
        return

    import ctypes
    from ctypes import wintypes

    MOD_ALT, MOD_CONTROL, MOD_NOREPEAT = 0x0001, 0x0002, 0x4000
    WM_HOTKEY, VK_G, HOTKEY_ID = 0x0312, 0x47, 1

    user32 = ctypes.windll.user32
    if not user32.RegisterHotKey(None, HOTKEY_ID, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, VK_G):
        log("Could not register Ctrl+Alt+G (already taken?) — hotkey disabled. "
            "Use update_now.bat instead.")
        return

    log("Hotkey ready: press Ctrl+Alt+G any time to push a dashboard update.")
    msg = wintypes.MSG()
    try:
        while not stop.is_set():
            # PeekMessage rather than GetMessage so the thread can observe `stop`.
            if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                    events.put(("hotkey Ctrl+Alt+G", 0, 0))
            else:
                time.sleep(0.1)
    finally:
        user32.UnregisterHotKey(None, HOTKEY_ID)


# ── trigger: safety net ───────────────────────────────────────────────────────

def safety_net_trigger(stop):
    if SAFETY_NET_SEC <= 0:
        log("Safety-net check disabled.")
        return
    while not stop.is_set():
        stop.wait(SAFETY_NET_SEC)
        if stop.is_set():
            break
        events.put(("safety-net check", 0, 0))


# ── main loop ─────────────────────────────────────────────────────────────────

def main():
    if "--tail" in sys.argv:
        return tail_mode()

    stop = threading.Event()

    threads = [
        threading.Thread(target=log_trigger, args=(stop,), daemon=True),
        threading.Thread(target=process_trigger, args=(stop,), daemon=True),
        threading.Thread(target=hotkey_trigger, args=(stop,), daemon=True),
        threading.Thread(target=safety_net_trigger, args=(stop,), daemon=True),
    ]

    log("GSPro Dashboard watcher started (event-driven; no fixed polling).")
    for t in threads:
        t.start()

    pending = []  # [(due_at, reason, retries_left)]
    try:
        while True:
            # Collect anything the trigger threads raised.
            try:
                while True:
                    reason, delay, retries = events.get_nowait()
                    pending.append((time.time() + delay, reason, retries))
            except queue.Empty:
                pass

            now = time.time()
            due = [p for p in pending if p[0] <= now]
            if due:
                # Coalesce: several signals for the same round finish are one update.
                pending = [p for p in pending if p[0] > now]
                reason = " + ".join(sorted({d[1] for d in due}))
                retries = max(d[2] for d in due)
                manual = "hotkey" in reason

                result = runner.check_and_update(reason, force=manual)

                if result == "no-new" and retries > 0:
                    wait = ROUND_END_RETRY_SEC[len(ROUND_END_RETRY_SEC) - retries]
                    log(f"  Portal has nothing new yet — re-checking in {wait}s.")
                    pending.append((time.time() + wait, reason, retries - 1))
                elif result == "busy":
                    pending.append((time.time() + 30, reason, retries))

            time.sleep(1)
    except KeyboardInterrupt:
        log("Watcher stopped.")
        stop.set()


def tail_mode():
    """
    Print GSPro's log live so you can find the real round-completion line and
    set GSPRO_ROUND_END_PATTERN accordingly. Lines matching the current
    pattern are marked with >>.
    """
    path = find_gspro_log()
    if not path:
        log("No GSPro log found. Set GSPRO_LOG_PATH to the log you want to tail.")
        return 1

    log(f"Tailing {path} — finish a round and watch for the line that marks it.")
    log("Press Ctrl+C to stop.")
    stop = threading.Event()

    def on_line(line):
        mark = ">>" if ROUND_END_PATTERN.search(line) else "  "
        print(f"{mark} {line}", flush=True)

    try:
        _tail_lines(path, on_line, stop)
    except KeyboardInterrupt:
        stop.set()
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
