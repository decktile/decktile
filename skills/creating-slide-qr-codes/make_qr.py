"""Make a QR code PNG with an optional logo in the middle.

Usage: pdm run python make_qr.py URL OUT.png [--icon LOGO.png] [--color '#003841']
"""
import argparse
import io

import segno
from PIL import Image

p = argparse.ArgumentParser()
p.add_argument("url")
p.add_argument("out")
p.add_argument("--icon", help="logo placed in the centre on a white pad")
p.add_argument("--color", default="#003841", help="module colour; keep it dark")
p.add_argument("--icon-ratio", type=float, default=0.22, help="logo width / QR width; stay <= 0.25")
a = p.parse_args()

# error='h' recovers ~30% of modules, which is what lets the logo cover the centre
qr = segno.make(a.url, error="h", micro=False)
buf = io.BytesIO()
qr.save(buf, kind="png", scale=24, border=4, dark=a.color, light="#ffffff")
img = Image.open(buf).convert("RGBA")

if a.icon:
    w = img.width
    icon = Image.open(a.icon).convert("RGBA")
    side = int(w * a.icon_ratio)
    icon.thumbnail((side, side), Image.LANCZOS)
    pad = int(side * 0.18)
    tile = Image.new("RGBA", (icon.width + 2 * pad, icon.height + 2 * pad), "white")
    tile.paste(icon, (pad, pad), icon)
    img.paste(tile, ((w - tile.width) // 2, (w - tile.height) // 2))

img.convert("RGB").save(a.out, optimize=True)
print(f"{a.out}: version {qr.version}, error {qr.error}, {img.width}px")
