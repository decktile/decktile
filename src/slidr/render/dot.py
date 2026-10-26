"""Graphviz dot renderer for slidr.

Executes `dot` CLI to convert DOT language to SVG.
Font and colors come from CSS via tinycss2.

Falls back to code highlighting if dot is not installed.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


def render_dot_svg(content: str, font_family: str = "",
                   font_size: int = 14,
                   tag_colors: dict[str, tuple[str, str]] | None = None,
                   blueprint: bool = False) -> str | None:
    """Render DOT code to SVG. blueprint: palette for ::: card {blueprint}."""
    try:
        result = subprocess.run(
            ["dot", "-Tsvg"],
            input=_preprocess(content, font_family, font_size),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.stdout.strip():
            svg = result.stdout
            svg = _strip_xml_decl(svg)
            svg = _inject_theme_css(svg, font_family, tag_colors, content, blueprint)
            return svg
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _preprocess(content: str, font_family: str, font_size: int) -> str:
    """Inject default font/size before any nodes if not already set."""
    if "fontsize" not in content and "fontname" not in content:
        fam = font_family.split(",")[0].strip().strip('"') if font_family else "sans-serif"
        size = font_size or 12
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "{" in line:
                indent = " " * (len(line) - len(line.lstrip()) + 4)
                defaults = (
                    f'{indent}node [fontname="{fam}" fontsize={size}];\n'
                    f'{indent}edge [fontname="{fam}" fontsize={size - 2}];'
                )
                lines[i] = lines[i] + "\n" + defaults
                break
        content = "\n".join(lines)
    return content


def _strip_xml_decl(svg: str) -> str:
    if svg.startswith("<?xml"):
        svg = svg.split("?>", 1)[-1].lstrip()
    if svg.startswith("<!DOCTYPE"):
        svg = svg.split(">", 1)[-1].lstrip()
    return svg


# ::: card {blueprint} (base.css): light lines and translucent fills on the
# card's blue grid; tags keep their meaning as brighter accents
_BLUEPRINT_TAGS = {"green": ("rgba(126,226,168,0.20)", "#7ee2a8"),
                   "red": ("rgba(255,138,138,0.20)", "#ff8a8a"),
                   "cyan": ("rgba(103,216,255,0.22)", "#67d8ff"),
                   "yellow": ("rgba(255,209,102,0.20)", "#ffd166")}


def _inject_theme_css(svg: str, font_family: str,
                      tag_colors: dict[str, tuple[str, str]] | None,
                      source: str = "", blueprint: bool = False) -> str:
    """Inject a <style> block with colors from the (light) CSS theme.

    A diagram is a light panel, also on dark slides: the canvas gets the
    theme's light card colour unless DOT sets bgcolor. Inside a blueprint
    card it is transparent and drawn in the blueprint palette instead.

    Any CSS rule beats an SVG presentation attribute, so a theme rule
    would silently override colours/fonts the author set in DOT. Each
    group of rules is only injected when the DOT source leaves that
    attribute to the theme."""
    fam = font_family.split(",")[0].strip().strip('"') if font_family else "sans-serif"
    tags = tag_colors or {}
    if blueprint:
        canvas, default_fill, default_stroke = "none", "rgba(143,211,255,0.08)", "#8fd3ff"
        fg, line, cluster = "#eaf4ff", "#8fd3ff", "rgba(143,211,255,0.55); stroke-dasharray: 4 3"
        tag_fills = _BLUEPRINT_TAGS
    else:
        default_fill, default_stroke = tags.get("default", ("#fafafa", "#ddd"))
        canvas, fg, line, cluster = default_fill, "#333", "#333", default_stroke
        fallback = {"green": ("#e8f5e9", "#0fd05d"), "red": ("#ffebee", "#ff7a7a"),
                    "cyan": ("#e0f7fa", "#67d8ff"), "yellow": ("#fff9c4", "#ffd166")}
        tag_fills = {t: tags.get(t, c) for t, c in fallback.items()}
    # an explicit fontname wins, except CSS generic names: weasyprint
    # doesn't resolve those inside SVG and falls back to a serif
    named = {n.lower() for n in re.findall(r'fontname\s*=\s*"?([^",;\]]+)', source)}
    font = ("" if named - {"sans-serif", "serif", "monospace", "sans"}
            else f" font-family: {fam} !important;")
    # node outline: style=rounded draws a <path>, the rest <polygon>/<ellipse>
    shape = lambda sel: ", ".join(f"{sel} > {s}" for s in ("polygon", "path", "ellipse"))

    rules = []
    if "bgcolor" not in source:
        rules.append(f".graph > polygon {{ fill: {canvas} !important; stroke: none !important; }}")
    if "fillcolor" not in source:
        rules.append(f"{shape('.node')} {{ fill: {default_fill} !important; stroke: {default_stroke} !important; stroke-linejoin: round !important; }}")
        for tag, (fill, stroke) in tag_fills.items():
            rules.append(f"{shape('.node.' + tag)} {{ fill: {fill} !important; stroke: {stroke} !important; }}")
    if not re.search(r"\bcolor\s*=", source):  # \b: not fillcolor/fontcolor
        rules += [
            f".edge > path {{ stroke: {line} !important; }}",
            f".edge > polygon {{ fill: {line} !important; stroke: {line} !important; }}",
            f"{shape('.cluster')} {{ fill: none !important; stroke: {cluster} !important; }}",
        ]
    text_fill = "" if "fontcolor" in source else f" fill: {fg};"
    if text_fill or font:
        rules += [f"{sel} {{{text_fill}{font} }}" for sel in (".cluster > text", ".node text", ".edge text")]
    if rules and "</svg>" in svg:
        css = "    <style>\n" + "\n".join(f"      {r}" for r in rules) + "\n    </style>"
        svg = svg.replace("</svg>", f"{css}\n</svg>", 1)
    return svg
