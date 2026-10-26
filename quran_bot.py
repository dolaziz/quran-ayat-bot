#!/usr/bin/env python3
"""Quran ayat bot — posts a random ayah to X and/or Threads.

X:    single tweet when verse fits 280 chars; else a reply-thread (no truncation).
Threads: single post when verse fits 500 chars; else a thread sequence via
Zernio threadItems (root + replies, no truncation).

Both platforms are optional:
  - X runs only when the `xurl` CLI is installed and authenticated.
  - Threads runs when zernio_state.json exists with an api_key + account_id.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

API_URL = "https://api.alquran.cloud/v1/ayah/random/editions/quran-uthmani,en.sahih"
XURL = shutil.which("xurl") or "xurl"
ZERNIO_URL = "https://zernio.com/api/v1/posts"
ZERNIO_STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "zernio_state.json")
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quran_state.json")
THREADS_HANDLE = os.environ.get("THREADS_HANDLE", "").strip().lstrip("@")


def record_success(platform):
    """Record that a platform posted successfully (read by the retry cron)."""
    try:
        with open(STATE_FILE) as f:
            st = json.load(f)
    except (OSError, ValueError):
        st = {}
    st[f"{platform}_last_ok"] = datetime.now(timezone.utc).isoformat()
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(st, f, indent=2)
    os.replace(tmp, STATE_FILE)

MAX_TWEET = 280
THREADS_MAX = 500
CHUNK_MAX = 264  # per-tweet content budget in a thread (leaves room for "…")
MAX_TRIES = 6


def fetch_ayah():
    req = urllib.request.Request(API_URL, headers={"User-Agent": "hermes-quran-bot/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def extract(data):
    editions = data.get("data", [])
    if len(editions) < 2:
        raise RuntimeError("API returned fewer than 2 editions")
    arabic = editions[0]["text"]
    translation = editions[1]["text"]
    surah = editions[0]["surah"]
    return {
        "arabic": arabic,
        "translation": translation,
        "surah_name": surah["englishName"],
        "surah_num": surah["number"],
        "ayah_num": editions[0]["numberInSurah"],
    }


def build_full(ayah):
    ref = f"— {ayah['surah_name']} {ayah['surah_num']}:{ayah['ayah_num']}"
    return f"{ayah['arabic']}\n\n{ayah['translation']}\n\n{ref}", ref


def chunk_text(text, max_len=CHUNK_MAX):
    """Split text at whitespace into chunks each <= max_len."""
    words = text.split()
    chunks, cur = [], ""
    for w in words:
        if not cur:
            cur = w
        elif len(cur) + 1 + len(w) <= max_len:
            cur += " " + w
        else:
            chunks.append(cur)
            cur = w
    if cur:
        chunks.append(cur)
    return chunks


# ----------------------------- X -----------------------------

def xurl_cmd(args):
    proc = subprocess.run([XURL] + args, capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(f"xurl {' '.join(args[:2])} failed: {proc.stdout} {proc.stderr}")
    return proc.stdout


def get_tweet_id(result):
    return json.loads(result).get("data", {}).get("id", "?")


def post_x(full, ayah):
    """Post to X: single tweet if fits, else thread. Returns (first_id, mode)."""
    if len(full) <= MAX_TWEET:
        result = xurl_cmd(["post", full])
        return get_tweet_id(result), "single"
    ref = f"— {ayah['surah_name']} {ayah['surah_num']}:{ayah['ayah_num']}"
    arabic_parts = chunk_text(ayah["arabic"])
    trans_parts = chunk_text(ayah["translation"])
    parts = []
    for i, p in enumerate(arabic_parts):
        parts.append(p + " …" if i < len(arabic_parts) - 1 else p)
    for i, p in enumerate(trans_parts):
        parts.append(p + " …" if i < len(trans_parts) - 1 else p)
    if len(parts[-1]) + 2 + len(ref) <= MAX_TWEET:
        parts[-1] = parts[-1] + "\n\n" + ref
    else:
        parts.append(ref)
    prev_id = None
    first = None
    for part in parts:
        result = xurl_cmd(["post", part]) if prev_id is None else xurl_cmd(["reply", prev_id, part])
        prev_id = get_tweet_id(result)
        if first is None:
            first = prev_id
    return first, f"thread({len(parts)})"


# ----------------------------- Threads -----------------------------

def load_zernio():
    try:
        with open(ZERNIO_STATE) as f:
            st = json.load(f)
    except (OSError, ValueError):
        return None
    if st.get("api_key") and st.get("account_id"):
        return st
    return None


def zernio_post(parts):
    """Post to Threads via Zernio. parts is a list of text chunks:
    [single] for one post, or [root, reply1, ...] for a thread sequence."""
    st = load_zernio()
    if not st:
        return None
    payload = {
        "platforms": [{"platform": "threads", "accountId": st["account_id"]}],
        "publishNow": True,
    }
    if len(parts) == 1:
        payload["content"] = parts[0]
    else:
        payload["content"] = parts[0]
        payload["threadItems"] = [{"content": p} for p in parts]
    req = urllib.request.Request(
        ZERNIO_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {st['api_key']}",
            "Content-Type": "application/json",
            "User-Agent": "hermes-quran-bot/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        raise RuntimeError(f"Zernio HTTP {e.code}: {body}")


def post_threads(full, ayah):
    """Post to Threads: single post if fits 500, else thread sequence."""
    if len(full) <= THREADS_MAX:
        resp = zernio_post([full])
        return resp, "single"
    ref = f"— {ayah['surah_name']} {ayah['surah_num']}:{ayah['ayah_num']}"
    arabic_parts = chunk_text(ayah["arabic"], max_len=480)
    trans_parts = chunk_text(ayah["translation"], max_len=480)
    parts = []
    for i, p in enumerate(arabic_parts):
        parts.append(p + " …" if i < len(arabic_parts) - 1 else p)
    for i, p in enumerate(trans_parts):
        parts.append(p + " …" if i < len(trans_parts) - 1 else p)
    if len(parts[-1]) + 2 + len(ref) <= THREADS_MAX:
        parts[-1] = parts[-1] + "\n\n" + ref
    else:
        parts.append(ref)
    resp = zernio_post(parts)
    return resp, f"sequence({len(parts)})"


# ----------------------------- main -----------------------------

def main():
    parser = argparse.ArgumentParser(description="Quran ayat bot — X and/or Threads")
    parser.add_argument(
        "--platforms",
        choices=["both", "x", "threads"],
        default="both",
        help="which platform(s) to post to (default: both)",
    )
    args = parser.parse_args()

    ayah = None
    full = ""
    for attempt in range(MAX_TRIES):
        try:
            ayah = extract(fetch_ayah())
        except Exception:
            if attempt == MAX_TRIES - 1:
                raise
            continue
        full, ref = build_full(ayah)
        if len(full) <= MAX_TWEET:
            break

    results = []
    urls = []
    posted_any = False

    # X
    if args.platforms in ("both", "x"):
        if shutil.which("xurl"):
            xid, xmode = post_x(full, ayah)
            results.append(f"X: {xmode}, id {xid}")
            urls.append("x: https://x.com/i/status/" + xid)
            record_success("x")
            posted_any = True
        else:
            results.append("X: skipped (xurl CLI not installed)")

    # Threads (if Zernio configured)
    if args.platforms in ("both", "threads"):
        if load_zernio():
            resp, tmode = post_threads(full, ayah)
            record_success("threads")
            post_id = None
            if resp and resp.get("post"):
                post_id = resp["post"].get("_id")
            results.append(f"Threads: {tmode}, zernio_id {post_id}")
            if THREADS_HANDLE:
                urls.append(f"threads: https://www.threads.net/@{THREADS_HANDLE}")
            posted_any = True
        else:
            results.append("Threads: skipped (no zernio_state.json)")

    preview = full.split("\n")[0][:60]
    if posted_any:
        print(f"✅ Posted ({len(full)} chars): {preview}")
    else:
        print("⚠️  Nothing posted — no platform is configured.")
        print(f"   Verse would have been ({len(full)} chars): {preview}")
    print("   " + "\n   ".join(results))
    for u in urls:
        print("   " + u)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Quran bot failed: {e}", file=sys.stderr)
        sys.exit(1)
