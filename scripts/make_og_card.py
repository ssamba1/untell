"""Regenerate docs/og.png — the social card every link share previews.

Kept in the repo because the card is a CLAIM SURFACE: it renders a headline that must stay true, and
a binary nobody can regenerate is a claim nobody can correct. The previous card said "the
open-source AI humanizer that closes the loop" and kept saying it after the README had moved on,
which is exactly the drift this file exists to make cheap to fix.

The figure on the card is Result 154: at tier=full and the shipped 0.45 verdict bar, the bundled
local ensemble flagged 5 of 30 genuine human HC3 answers. Attributed to THIS repo's ensemble on the
card, not to detectors in general — the distinction is the difference between a measurement and a
slogan.

    python scripts/make_og_card.py
"""
import os

from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 640
BG, FG, DIM, ACC = (20, 18, 31), (240, 238, 248), (150, 146, 170), (138, 43, 226)

def font(px, bold=False):
    names = ["segoeuib.ttf", "seguisb.ttf"] if bold else ["segoeui.ttf"]
    names += ["arialbd.ttf"] if bold else ["arial.ttf"]
    for n in names:
        p = os.path.join(r"C:\Windows\Fonts", n)
        if os.path.exists(p):
            return ImageFont.truetype(p, px)
    return ImageFont.load_default()

im = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(im)

# accent bar
d.rectangle([0, 0, 10, H], fill=ACC)

x = 74
d.text((x, 92),  "untell", font=font(96, True), fill=FG)
d.text((x, 210), "an AI-detector auditing toolkit", font=font(44, True), fill=ACC)

body = [
    "Measures what a detector's verdict is actually worth:",
    "false-positive rate on genuine human writing, verdict",
    "stability across seeds, and whether that verdict survives",
    "meaning-preserving edits.",
]
y = 292
for line in body:
    d.text((x, y), line, font=font(31), fill=DIM)
    y += 44

# the finding, as the card's payload
d.rectangle([x, 492, x + 1000, 496], fill=(52, 48, 72))
d.text((x, 522), "Its own bundled ensemble flags 17% of genuine human writing",
       font=font(29, True), fill=FG)
d.text((x, 566), "Claude Code skill + Python CLI   ·   MIT   ·   every number reproducible",
       font=font(25), fill=DIM)

im.save(r"C:\Users\Admin\Humanize\docs\og.png", optimize=True)
print("wrote og.png", im.size)
