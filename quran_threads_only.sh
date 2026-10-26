#!/bin/bash
# Threads-only run of the Quran ayat bot.
# Use this as the cron command when you want extra Threads posts without
# also posting to X.
cd "$(dirname "$0")" && exec python3 quran_bot.py --platforms threads
