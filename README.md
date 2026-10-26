# Quran Ayat Bot

Posts a random Quran verse — Arabic (Uthmani script) + English translation (Sahih International) + surah reference — to **X/Twitter** and **Threads**.

Built to post twice daily to X and four times daily to Threads. Handles long verses without truncation by automatically threading them.

```
وَلَقَدْ صَرَّفْنَا فِى هَٰذَا ٱلْقُرْءَانِ لِيَذَّكَّرُوا۟

And We have certainly diversified for the people in this Qur'an...

— Al-Isra 17:41
```

## Features

- **Random ayah** fetched from the free [alquran.cloud](https://alquran.cloud) API (no key needed)
- **Uthmani script + Sahih International** translation
- **No truncation** — long verses automatically become a thread
  - X: reply chain (280-char limit per tweet)
  - Threads: `threadItems` thread sequence (500-char limit per post)
- **Dual-platform** — X via the [`xurl`](https://github.com/xdevplatform/xurl) CLI, Threads via the [Zernio](https://zernio.com) API
- **Optional retry watchdog** — detects missed slots and re-posts
- **Optional ayah card generator** — renders a 1080×1350 PNG with Arabic calligraphy (`quran_card.py`)

## Quick start

### 1. Install dependencies

```bash
pip install -r requirements.txt   # only Pillow, and only for quran_card.py
```

The posting script itself uses only the Python standard library.

### 2. Configure Threads (optional)

Threads posting goes through [Zernio](https://zernio.com), which wraps Meta's official Threads API — so you don't need a Meta developer account or app review.

1. Sign up at [zernio.com](https://zernio.com) (first 2 connected accounts are free)
2. Connect your Threads account in the dashboard
3. Copy your **API key** and **Account ID**
4. Create the state file:

```bash
cp zernio_state.example.json zernio_state.json
chmod 600 zernio_state.json
# then edit it with your real key + account id
```

### 3. Configure X (optional)

Install and authenticate the `xurl` CLI:

```bash
curl -fsSL https://raw.githubusercontent.com/xdevplatform/xurl/main/install.sh | bash
xurl auth apps add my-app --client-id YOUR_ID --client-secret YOUR_SECRET
xurl auth oauth2 --app my-app
```

X posting is skipped automatically if `xurl` isn't installed.

### 4. Run it

```bash
# Post to every configured platform
python3 quran_bot.py

# Only Threads
python3 quran_bot.py --platforms threads

# Only X
python3 quran_bot.py --platforms x
```

## Scheduling

Cron examples (times shown in the server's local timezone — adjust to yours):

```cron
# X + Threads twice a day
0 8,20 * * *  cd /path/to/bot && python3 quran_bot.py

# Extra Threads-only runs
0 2,14 * * *  cd /path/to/bot && python3 quran_bot.py --platforms threads

# Retry watchdog, one hour after each slot (silent when nothing is missed)
5 3,9,15,21 * * *  cd /path/to/bot && python3 quran_retry.py
```

`quran_retry.py` compares each platform's last successful post time (stored in
`quran_state.json`) against the expected slot, and only re-posts what's missing.

## Ayah cards (optional)

`quran_card.py` renders a verse as a shareable image — deep navy background, gold Arabic calligraphy in the [Amiri Quran](https://github.com/aliftype/amiri) font, translation, and reference.

```bash
python3 quran_card.py           # prints the generated PNG path
```

Requires system fonts for Arabic. On Debian/Ubuntu:

```bash
sudo apt install fonts-noto-core
# For the Amiri Quran font (recommended):
# download from https://github.com/aliftype/amiri/releases and install to /usr/share/fonts/
```

`Pillow` must be built with **raqm** support for correct Arabic shaping:

```python
from PIL import features
print(features.check("raqm"))   # should be True
```

## Configuration

| Env var | Purpose |
|---|---|
| `THREADS_HANDLE` | Your Threads username, used only for the printed post URL |

| File | Purpose |
|---|---|
| `zernio_state.json` | Zernio API key + Threads account ID (**never commit**) |
| `quran_state.json` | Last-successful-post timestamps, used by the watchdog |

## How the threading works

Verses longer than the platform limit are split at word boundaries — never mid-word, never truncated:

- **Arabic** chunks are marked with a trailing `…` where the verse continues
- **Translation** follows the same chunking
- **Reference** (`— Surah A:B`) lands on the final post

Text is split with a whitespace-aware packer, so each chunk fits the budget while losing nothing.

## Notes

- The alquran.cloud API is free and requires no authentication.
- Zernio's free tier covers two connected accounts — enough for one bot.
- Arabic rendering needs a font with proper glyph coverage; `Amiri Quran` is the best choice for Quranic text.

## License

MIT — see [LICENSE](LICENSE).
