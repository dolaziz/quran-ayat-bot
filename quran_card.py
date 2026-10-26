#!/usr/bin/env python3
"""Generate ayah calligraphy cards (1080x1350, Instagram 4:5) with Arabic
calligraphy, Sahih International translation, and reference.

Uses Amiri Quran for the Arabic (proper RTL via raqm) and a deep teal/gold
palette. Saves PNG to /tmp/quran_card_<surah>-<ayah>.png and prints the path.
"""
import json
import os
import sys
import urllib.request
from PIL import Image, ImageDraw, ImageFont, ImageFilter

API_URL = "https://api.alquran.cloud/v1/ayah/random/editions/quran-uthmani,en.sahih"

W, H = 1080, 1350
BG = (13, 27, 42)       # deep midnight
ACCENT = (201, 169, 96) # gold
TEXT = (232, 230, 227)  # warm white
MUTED = (150, 165, 180) # slate

FONT_QURAN = "/usr/share/fonts/truetype/amiri/AmiriQuran.ttf"
FONT_AR = "/usr/share/fonts/truetype/amiri/Amiri-Regular.ttf"
FONT_EN = "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"


def fetch_ayah():
    req = urllib.request.Request(API_URL, headers={"User-Agent": "hermes-quran-bot/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
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


def wrap_rtl(draw, text, font, max_width):
    """Wrap text (RTL-safe) into lines that fit max_width."""
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=font) <= max_width or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def draw_centered(draw, lines, font, y, max_width, fill, line_gap=None):
    """Draw lines centered horizontally starting at y. Returns new y."""
    line_gap = line_gap or int(font.size * 0.35)
    for line in lines:
        w = draw.textlength(line, font=font)
        draw.text(((W - w) / 2, y), line, font=font, fill=fill)
        y += font.size + line_gap
    return y


def make_card(ayah, out_path):
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # soft radial glow behind the text
    glow = Image.new("L", (W, H), 0)
    gd = ImageDraw.Draw(glow)
    gd.ellipse((W * 0.2, H * 0.22, W * 0.8, H * 0.72), fill=60)
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    img.paste((0, 0, 0), (0, 0), mask=glow)
    # re-create draw (mask paste flattened)
    draw = ImageDraw.Draw(img)

    # top ornament: gold line
    draw.line((W * 0.28, 110, W * 0.72, 110), fill=ACCENT, width=2)
    draw.line((W * 0.34, 118, W * 0.66, 118), fill=ACCENT, width=1)

    # Bismillah-ish header: surah name
    f_surah = ImageFont.truetype(FONT_EN, 46)
    surah_text = f"Surah {ayah['surah_name']} · Ayah {ayah['ayah_num']}"
    sw = draw.textlength(surah_text, font=f_surah)
    draw.text(((W - sw) / 2, 180), surah_text, font=f_surah, fill=MUTED)

    # Arabic calligraphy
    f_arabic = ImageFont.truetype(FONT_QURAN, 88)
    arabic_lines = wrap_rtl(draw, ayah["arabic"], f_arabic, int(W * 0.82))
    # cap font size if too many lines
    while len(arabic_lines) > 9 and f_arabic.size > 40:
        f_arabic = ImageFont.truetype(FONT_QURAN, f_arabic.size - 8)
        arabic_lines = wrap_rtl(draw, ayah["arabic"], f_arabic, int(W * 0.82))

    y = 340
    y = draw_centered(draw, arabic_lines, f_arabic, y, int(W * 0.82), ACCENT, line_gap=30)

    # center ornament
    y += 40
    draw.line((W * 0.30, y, W * 0.70, y), fill=ACCENT, width=2)
    draw.ellipse((W / 2 - 9, y - 9, W / 2 + 9, y + 9), outline=ACCENT, width=2)
    y += 60

    # Translation
    f_trans = ImageFont.truetype(FONT_EN, 42)
    trans_lines = wrap_rtl(draw, ayah["translation"], f_trans, int(W * 0.78))
    while len(trans_lines) > 9 and f_trans.size > 28:
        f_trans = ImageFont.truetype(FONT_EN, f_trans.size - 4)
        trans_lines = wrap_rtl(draw, ayah["translation"], f_trans, int(W * 0.78))
    y = draw_centered(draw, trans_lines, f_trans, y, int(W * 0.78), TEXT, line_gap=24)

    # footer reference
    ref = f"— {ayah['surah_name']} {ayah['surah_num']}:{ayah['ayah_num']}"
    f_ref = ImageFont.truetype(FONT_AR, 40)
    rw = draw.textlength(ref, font=f_ref)
    draw.text(((W - rw) / 2, H - 150), ref, font=f_ref, fill=MUTED)

    draw.line((W * 0.28, H - 95, W * 0.72, H - 95), fill=ACCENT, width=2)
    draw.line((W * 0.34, H - 87, W * 0.66, H - 87), fill=ACCENT, width=1)

    img.save(out_path, "PNG")
    return out_path


def main():
    data = fetch_ayah()
    ayah = extract(data)
    out = f"/tmp/quran_card_{ayah['surah_num']}-{ayah['ayah_num']}.png"
    make_card(ayah, out)
    print(out)
    print(json.dumps(ayah, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Card generation failed: {e}", file=sys.stderr)
        sys.exit(1)
