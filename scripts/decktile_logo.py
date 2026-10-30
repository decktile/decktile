#!/usr/bin/env python3
"""Generate the decktile logo: mark, wordmark lockup, and PNG exports.

The mark is a stack of slide cards seen at a slight angle; the top card shows
a 2x2 tile grid, decktile's card/grid layout. Wordmark text is converted to
SVG paths so the files need no font installed.
"""

import argparse
from pathlib import Path

INK = "#0f172a"
TEAL = "#0d9488"
TEAL_LIGHT = "#5eead4"
AMBER = "#f59e0b"
BACK_CARD = "#cbd5e1"
MID_CARD = "#94a3b8"


class DecktileLogo:
    def __init__(self, out: Path, font: str):
        self.out = out
        self.font = font
        self.out.mkdir(parents=True, exist_ok=True)

    # --- mark -----------------------------------------------------------
    def mark_body(self, dark: bool = False) -> str:
        """Mark drawn in a 256x256 box."""
        back = "#334155" if dark else BACK_CARD
        mid = "#475569" if dark else MID_CARD
        face = "#0b1220" if dark else "#ffffff"
        stroke = TEAL_LIGHT if dark else INK
        tile = TEAL_LIGHT if dark else TEAL
        tile_soft = "#1e3a3a" if dark else "#ccfbf1"
        # three stacked cards, the front one carries a 2x2 grid of tiles
        return f"""
  <g transform="translate(128 128) rotate(-8) translate(-128 -128)">
    <rect x="58" y="34" width="168" height="168" rx="26" fill="{back}"/>
  </g>
  <g transform="translate(128 128) rotate(-3) translate(-128 -128)">
    <rect x="44" y="44" width="168" height="168" rx="26" fill="{mid}"/>
  </g>
  <rect x="30" y="54" width="168" height="168" rx="26" fill="{face}" stroke="{stroke}" stroke-width="10"/>
  <rect x="56" y="80"  width="54" height="54" rx="10" fill="{tile}"/>
  <rect x="118" y="80" width="54" height="54" rx="10" fill="{tile_soft}"/>
  <rect x="56" y="142" width="54" height="54" rx="10" fill="{tile_soft}"/>
  <rect x="118" y="142" width="54" height="54" rx="10" fill="{AMBER}"/>"""

    def mark_svg(self, dark: bool = False, bg: str | None = None) -> str:
        bg_rect = f'<rect width="256" height="256" rx="56" fill="{bg}"/>' if bg else ""
        body = self.mark_body(dark)
        if bg:  # padding inside the avatar square
            body = f'<g transform="translate(128 128) scale(0.8) translate(-128 -128)">{body}</g>'
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" '
                f'width="256" height="256">{bg_rect}{body}\n</svg>\n')

    # --- wordmark -------------------------------------------------------
    def text_path(self, text: str, size: float) -> tuple[str, float, float]:
        """Return (path d, advance width, ascender) for text at `size` px."""
        from fontTools.pens.svgPathPen import SVGPathPen
        from fontTools.pens.transformPen import TransformPen
        from fontTools.ttLib import TTFont

        f = TTFont(self.font)
        upm = f["head"].unitsPerEm
        scale = size / upm
        cmap = f.getBestCmap()
        gs = f.getGlyphSet()
        hmtx = f["hmtx"]
        pen = SVGPathPen(gs)
        x = 0.0
        for ch in text:
            g = cmap[ord(ch)]
            gs[g].draw(TransformPen(pen, (scale, 0, 0, -scale, x, 0)))
            x += hmtx[g][0] * scale
        asc = f["OS/2"].sCapHeight * scale if hasattr(f["OS/2"], "sCapHeight") else size * 0.7
        return pen.getCommands(), x, asc

    def lockup_svg(self, dark: bool = False) -> str:
        size = 150
        d1, w1, cap = self.text_path("deck", size)
        d2, w2, _ = self.text_path("tile", size)
        ink = "#f8fafc" if dark else INK
        accent = TEAL_LIGHT if dark else TEAL
        gap = 40
        tx = 256 + gap
        # baseline so the x-height sits on the mark's visual centre
        baseline = 128 + cap * 0.5 + 12
        width = int(tx + w1 + w2 + 24)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} 256" '
                f'width="{width}" height="256">{self.mark_body(dark)}\n'
                f'  <path transform="translate({tx} {baseline:.1f})" fill="{ink}" d="{d1}"/>\n'
                f'  <path transform="translate({tx + w1:.1f} {baseline:.1f})" fill="{accent}" d="{d2}"/>\n'
                f'</svg>\n')

    # --- export ---------------------------------------------------------
    def write(self, name: str, svg: str) -> Path:
        p = self.out / name
        p.write_text(svg, encoding="utf-8")
        return p

    @staticmethod
    def png(svg: Path, width: int) -> Path:
        import cairosvg

        out = svg.with_name(f"{svg.stem}-{width}.png")
        cairosvg.svg2png(url=str(svg), write_to=str(out), output_width=width)
        return out

    def build(self) -> list[Path]:
        files = [
            self.write("decktile-mark.svg", self.mark_svg()),
            self.write("decktile-mark-dark.svg", self.mark_svg(dark=True)),
            self.write("decktile-avatar.svg", self.mark_svg(bg="#f1f5f9")),
            self.write("decktile-logo.svg", self.lockup_svg()),
            self.write("decktile-logo-dark.svg", self.lockup_svg(dark=True)),
        ]
        pngs = [self.png(files[2], 500), self.png(files[0], 512), self.png(files[3], 1200),
                self.png(files[4], 1200)]
        return files + pngs


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("-o", "--out", type=Path, default=Path("logo"))
    p.add_argument("--font", required=True, help="TTF for the wordmark (converted to paths)")
    args = p.parse_args()
    for f in DecktileLogo(args.out, args.font).build():
        print(f)


if __name__ == "__main__":
    main()
