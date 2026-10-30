"""Lucide icon font: name -> glyph codepoint, parsed from the vendored
lucide.css codepoint map (src/slidr/assets/lucide/VENDORED.md).
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

FONT_DIR = Path(__file__).parent.parent / "assets" / "lucide"
FONT_PATH = FONT_DIR / "lucide.ttf"

_CODEPOINT_RE = re.compile(r'\.icon-([a-z0-9-]+)::before\s*\{\s*content:\s*"\\e([0-9a-f]+)"\s*;')


@lru_cache(maxsize=1)
def _codepoints() -> dict[str, str]:
    css = (FONT_DIR / "lucide.css").read_text(encoding="utf-8")
    return {name: chr(int("e" + hexcode, 16)) for name, hexcode in _CODEPOINT_RE.findall(css)}


def icon_glyph(name: str) -> str | None:
    """The single glyph character for a lucide icon name, or None if the
    vendored font doesn't have it."""
    return _codepoints().get(name)
