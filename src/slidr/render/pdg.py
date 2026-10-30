"""predictygraph renderer for slidr ```pdg blocks.

The slide theme's body font and tag colours are passed to predictygraph as a
stylesheet layered under the diagram's own css, so `node.green`, `node.cyan`,
`node.yellow` and `node.red` match slidr cards and anything in the block wins.
"""

from __future__ import annotations

import re

# ::: card {blueprint} (base.css): light lines and translucent fills on the
# card's blue grid; tags keep their meaning as brighter accents.
_BLUEPRINT_TAGS = {"default": ("rgba(143,211,255,0.08)", "#8fd3ff"),
                   "green": ("rgba(126,226,168,0.20)", "#7ee2a8"),
                   "red": ("rgba(255,138,138,0.20)", "#ff8a8a"),
                   "cyan": ("rgba(103,216,255,0.22)", "#67d8ff"),
                   "yellow": ("rgba(255,209,102,0.20)", "#ffd166")}
_BLUEPRINT_CSS = """\
graph { color: #eaf4ff; }
node { color: #eaf4ff; }
group { fill: none; stroke: rgba(143,211,255,0.55); stroke-dasharray: 4 3; color: #8fd3ff; }
edge { stroke: #8fd3ff; color: #eaf4ff; }"""


def theme_css(font_family: str = "", font_size: int = 0,
              tag_colors: dict[str, tuple[str, str]] | None = None) -> str:
    """Slide theme as a predictygraph stylesheet."""
    rules = []
    graph = []
    if font_family:
        graph.append(f"font-family: {font_family};")
    if font_size:
        graph.append(f"font-size: {int(font_size)}px;")
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


def render_pdg_svg(content: str, font_family: str = "", font_size: int = 0,
                   tag_colors: dict[str, tuple[str, str]] | None = None,
                   blueprint: bool = False) -> str | None:
    """Render a predictygraph diagram to SVG, or None if it fails to parse.

    blueprint: palette for ``::: card {blueprint}`` (light lines, translucent fills).
    """
    import predictygraph

    css = theme_css(font_family, font_size, _BLUEPRINT_TAGS if blueprint else tag_colors)
    if blueprint:
        css += "\n" + _BLUEPRINT_CSS
    # Theme goes first so css inside the block overrides it.
    text = "css {\n" + css + "\n}\n" + content
    try:
        svg = predictygraph.render(text, t=0)
    except Exception:
        return None
    return _strip_xml_decl(svg)


def _strip_xml_decl(svg: str) -> str:
    return re.sub(r"^\s*<\?xml[^>]*\?>\s*", "", svg)
