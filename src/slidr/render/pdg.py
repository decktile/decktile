"""predictygraph renderer for slidr ```pdg blocks.

The slide theme's body font and tag colours are passed to predictygraph as a
stylesheet layered under the diagram's own css, so `node.green`, `node.cyan`,
`node.yellow` and `node.red` match slidr cards and anything in the block wins.
"""

from __future__ import annotations

import re


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
                   tag_colors: dict[str, tuple[str, str]] | None = None) -> str | None:
    """Render a predictygraph diagram to SVG, or None if it fails to parse."""
    import predictygraph

    # Theme goes first so css inside the block overrides it.
    text = "css {\n" + theme_css(font_family, font_size, tag_colors) + "\n}\n" + content
    try:
        svg = predictygraph.render(text, t=0)
    except Exception:
        return None
    return _strip_xml_decl(svg)


def _strip_xml_decl(svg: str) -> str:
    return re.sub(r"^\s*<\?xml[^>]*\?>\s*", "", svg)
