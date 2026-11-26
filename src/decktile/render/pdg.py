# SPDX-FileCopyrightText: 2026 Reza Jelveh
#
# SPDX-License-Identifier: Apache-2.0

"""predictygraph renderer for decktile ``pdg`` fenced blocks.

The slide theme's body font and tag colours are passed to predictygraph as a
stylesheet layered under the diagram's own css, so ``node.green``, ``node.cyan``,
``node.yellow`` and ``node.red`` match decktile cards and anything in the block wins.
"""

from __future__ import annotations

import re

# ::: card {blueprint} (base.css): light lines and translucent fills on the
# card's blue grid; tags keep their meaning as brighter accents.
_BLUEPRINT_TAGS = {
    "default": ("rgba(143,211,255,0.08)", "#8fd3ff"),
    "green": ("rgba(126,226,168,0.20)", "#7ee2a8"),
    "red": ("rgba(255,138,138,0.20)", "#ff8a8a"),
    "cyan": ("rgba(103,216,255,0.22)", "#67d8ff"),
    "yellow": ("rgba(255,209,102,0.20)", "#ffd166"),
}
_BLUEPRINT_CSS = """\
graph { color: #eaf4ff; }
node { color: #eaf4ff; }
group { fill: none; stroke: rgba(143,211,255,0.55); stroke-dasharray: 4 3; color: #8fd3ff; }
edge { stroke: #8fd3ff; color: #eaf4ff; }"""


def theme_css(font_family: str = "", font_size: float = 0, tag_colors: dict[str, tuple[str, str]] | None = None) -> str:
    """Slide theme as a predictygraph stylesheet."""
    rules = []
    graph = []
    if font_family:
        graph.append(f"font-family: {font_family};")
    if font_size:
        graph.append(f"font-size: {font_size:g}px;")
    if graph:
        rules.append("graph { " + " ".join(graph) + " }")
    for tag, (fill, stroke) in (tag_colors or {}).items():
        decl = []
        if fill:
            decl.append(f"fill: {fill};")
        if stroke:
            decl.append(f"stroke: {stroke};")
        if not decl:
            continue
        sel = "node" if tag == "default" else f"node.{tag}"
        rules.append(f"{sel} {{ " + " ".join(decl) + " }")
    return "\n".join(rules)


def render_pdg_svg(
    content: str,
    font_family: str = "",
    font_size: float = 0,
    tag_colors: dict[str, tuple[str, str]] | None = None,
    blueprint: bool = False,
    animated: bool = False,
    theme: str = "",
    flush: bool = False,
    min_width: float = 0,
) -> str | None:
    """Render a predictygraph diagram to SVG, or None if it fails to parse.

    ``blueprint`` uses the palette for ``::: card {blueprint}`` (light lines,
    translucent fills). ``animated`` keeps predictygraph's SMIL animation
    (``flow=``, ``border=``) for HTML; the default is a still frame, which PDF
    and ODP need. ``theme`` is the deck's ``pdg_theme`` (a predictygraph theme
    name), it replaces the slide's tag colours, the slide
    font still applies. ``flush`` drops the diagram's outer margin (``::: stack``), so
    its boxes line up with the blocks above and below; ``graph padding=`` still wins.
    """
    import predictygraph

    own_theme = bool(_OWN_THEME.search(content))
    deck_theme = theme if theme and not blueprint and not own_theme else None
    css = theme_css(font_family, font_size, _BLUEPRINT_TAGS if blueprint else None if deck_theme else tag_colors)
    if blueprint:
        css += "\n" + _BLUEPRINT_CSS
    # A diagram's own theme= wins over the slide theme; otherwise slide theme
    # goes first so css inside the block overrides it.
    text = content if own_theme else "css {\n" + css + "\n}\n" + content
    graph = ("padding: 0; " if flush else "") + (f"min-width: {min_width:.2f}px; " if min_width else "")
    if graph:
        text = "css { graph { " + graph + "} }\n" + text
    try:
        svg = predictygraph.render(text, t=None if animated else 0, theme=deck_theme)
    except Exception:
        return None
    return _strip_xml_decl(svg)


_OWN_THEME = re.compile(r"^\s*graph\b[^\n]*\stheme=", re.M)


def _strip_xml_decl(svg: str) -> str:
    return re.sub(r"^\s*<\?xml[^>]*\?>\s*", "", svg)
