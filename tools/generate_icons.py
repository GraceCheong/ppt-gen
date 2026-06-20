"""
아이콘 PNG 생성 — PIL 드로잉, 50x50.
assets/icons/ 에 저장.
"""
from pathlib import Path
from PIL import Image, ImageDraw
import math, os

OUT = Path(__file__).parent.parent / "assets" / "icons"
OUT.mkdir(parents=True, exist_ok=True)

S = 50          # canvas size
FG     = (80, 90, 105)
DANGER = (180, 45, 90)
ACCENT = (60, 130, 200)


def new(color=FG):
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img), color


def save(img, name):
    img.save(OUT / f"{name}.png")
    print(f"  {name}.png")


# ── edit  ✏️  (emoji via Segoe UI Emoji) ─────────────────────────
_emoji_font = "C:/Windows/Fonts/seguiemj.ttf"
if os.path.exists(_emoji_font):
    from PIL import ImageFont
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(_emoji_font, 40)
    d.text((2, 2), "✏", font=font, embedded_color=True)
    save(img, "edit")
else:
    img, d, c = new()
    # pencil diagonal
    w = 4
    d.line([(12, 36), (36, 12)], fill=c, width=w)
    d.polygon([(8, 40), (12, 36), (14, 38)], fill=c)
    d.polygon([(34, 10), (38, 8), (40, 12), (36, 14)], fill=(180, 100, 100))
    save(img, "edit")

# ── trash 🗑 ──────────────────────────────────────────────────────
img, d, c = new(DANGER)
# handle
d.rectangle([18, 6, 32, 10], fill=c)
# lid
d.rectangle([10, 10, 40, 14], fill=c)
# body
d.rectangle([13, 15, 37, 42], outline=c, width=3)
# vertical lines
for x in [21, 29]:
    d.line([(x, 18), (x, 39)], fill=c, width=2)
save(img, "trash")

# ── refresh ↺ ────────────────────────────────────────────────────
img, d, c = new()
cx, cy, r = 25, 25, 15
pts = []
for deg in range(40, 320, 6):
    rad = math.radians(deg)
    pts.append((cx + r * math.cos(rad), cy + r * math.sin(rad)))
for i in range(len(pts) - 1):
    d.line([pts[i], pts[i+1]], fill=c, width=3)
# arrowhead
e = pts[-1]
d.polygon([(e[0]-6, e[1]), (e[0]+2, e[1]-6), (e[0]+2, e[1]+6)], fill=c)
save(img, "refresh")

# ── download ⬇ ───────────────────────────────────────────────────
img, d, c = new(ACCENT)
d.line([(25, 6), (25, 30)], fill=c, width=4)
d.polygon([(25, 38), (14, 24), (36, 24)], fill=c)
d.line([(10, 42), (40, 42)], fill=c, width=4)
save(img, "download")

# ── plus + ───────────────────────────────────────────────────────
img, d, c = new()
d.line([(25, 8), (25, 42)], fill=c, width=4)
d.line([(8, 25), (42, 25)], fill=c, width=4)
save(img, "plus")

# ── search 🔍 ─────────────────────────────────────────────────────
img, d, c = new()
d.ellipse([6, 6, 32, 32], outline=c, width=4)
d.line([(28, 28), (44, 44)], fill=c, width=4)
save(img, "search")

print("Done →", OUT)
