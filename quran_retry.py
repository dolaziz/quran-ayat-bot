#!/usr/bin/env python3
"""Retry a missed quran-bot slot ~1h after the scheduled run failed.

Run by cron at :05 of hours 3,9,15,21 SGT (one hour after the main slots
02,08,14,20 SGT). Silent (empty stdout) when the slot already posted
successfully; otherwise re-posts the missing platform(s) and reports it.

Platform split: slots 08 & 20 SGT post X + Threads;
slots 02 & 14 SGT post Threads only.

NOTE: the cron scheduler on this box interprets expressions in SGT (+08),
so all slot hours here are SGT.
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE, "quran_state.json")
BOT = os.path.join(BASE, "quran_bot.py")

SGT = timezone(timedelta(hours=8))

# main slot hour (SGT) -> platforms that should have posted
SLOTS = {2: ["threads"], 8: ["x", "threads"], 14: ["threads"], 20: ["x", "threads"]}


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def missing_platforms(slot_hour, st, slot_start):
    missing = []
    for p in SLOTS[slot_hour]:
        last = st.get(f"{p}_last_ok")
        ok = False
        if last:
            try:
                ok = datetime.fromisoformat(last) >= slot_start
            except ValueError:
                ok = False
        if not ok:
            missing.append(p)
    return missing


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", type=int, default=None,
                        help="force slot hour (local tz); default derive from current hour")
    parser.add_argument("--dry-run", action="store_true", help="report without posting")
    args = parser.parse_args()

    now = datetime.now(SGT)
    if args.slot is not None:
        slot_hour = args.slot
    else:
        slot_hour = now.hour - 1
        if slot_hour not in SLOTS:
            # not running right after a main slot — nothing to do
            return

    slot_start = now.replace(hour=slot_hour, minute=0, second=0, microsecond=0)
    st = load_state()
    missing = missing_platforms(slot_hour, st, slot_start)
    if not missing:
        return  # silent: slot already posted

    platforms = ",".join(missing)
    # quran_bot.py --platforms accepts only "both" | "x" | "threads"
    platforms_arg = "both" if set(missing) == {"x", "threads"} else missing[0]
    if args.dry_run:
        print(f"[dry-run] slot {slot_hour:02d}:00 missed platforms: {platforms} — would retry now")
        return

    cmd = [sys.executable, BOT, "--platforms", platforms_arg]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
    if proc.returncode == 0:
        print(f"🔄 Retried missed slot {slot_hour:02d}:00 ({platforms}):\n{proc.stdout.strip()}")
    else:
        print(f"❌ Retry for slot {slot_hour:02d}:00 failed: {proc.stderr.strip()}")
        sys.exit(1)


if __name__ == "__main__":
    main()
