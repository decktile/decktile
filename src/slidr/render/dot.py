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
                   tag_colors: dict[str, tuple[str, str]] | None = None) -> str | None:
    """Render DOT code to SVG."""
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
            svg = _inject_theme_css(svg, font_family, tag_colors, content)
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


def _inject_theme_css(svg: str, font_family: str,
                      tag_colors: dict[str, tuple[str, str]] | None,
                      source: str = "") -> str:
    """Inject a <style> block with colors from the (light) CSS theme.

    A diagram is always a light panel, also on dark slides: the canvas
    gets the theme's light card colour unless DOT sets bgcolor.

    Any CSS rule beats an SVG presentation attribute, so a theme rule
    would silently override colours/fonts the author set in DOT. Each
    group of rules is only injected when the DOT source leaves that
    attribute to the theme."""
    fam = font_family.split(",")[0].strip().strip('"') if font_family else "sans-serif"
    tags = tag_colors or {}
    default_fill, default_stroke = tags.get("default", ("#fafafa", "#ddd"))
    fg = "#333"
    # an explicit fontname wins, except CSS generic names: weasyprint
    # doesn't resolve those inside SVG and falls back to a serif
    named = {n.lower() for n in re.findall(r'fontname\s*=\s*"?([^",;\]]+)', source)}
    font = ("" if named - {"sans-serif", "serif", "monospace", "sans"}
            else f" font-family: {fam} !important;")
    # node outline: style=rounded draws a <path>, the rest <polygon>/<ellipse>
    shape = lambda sel: ", ".join(f"{sel} > {s}" for s in ("polygon", "path", "ellipse"))

    rules = []
    if "bgcolor" not in source:
        rules.append(f".graph > polygon {{ fill: {default_fill} !important; stroke: none !important; }}")
    if "fillcolor" not in source:
        rules.append(f"{shape('.node')} {{ fill: {default_fill} !important; stroke: {default_stroke} !important; stroke-linejoin: round !important; }}")
        fallback = {"green": ("#e8f5e9", "#0fd05d"), "red": ("#ffebee", "#ff7a7a"),
                    "cyan": ("#e0f7fa", "#67d8ff"), "yellow": ("#fff9c4", "#ffd166")}
        for tag, (fill, stroke) in fallback.items():
            fill, stroke = tags.get(tag, (fill, stroke))
            rules.append(f"{shape('.node.' + tag)} {{ fill: {fill} !important; stroke: {stroke} !important; }}")
    if not re.search(r"\bcolor\s*=", source):  # \b: not fillcolor/fontcolor
        rules += [
            f".edge > path {{ stroke: {fg} !important; }}",
            f".edge > polygon {{ fill: {fg} !important; stroke: {fg} !important; }}",
            f"{shape('.cluster')} {{ fill: none !important; stroke: {default_stroke} !important; }}",
        ]
    text_fill = "" if "fontcolor" in source else f" fill: {fg};"
    if text_fill or font:
        rules += [f"{sel} {{{text_fill}{font} }}" for sel in (".cluster > text", ".node text", ".edge text")]
    if rules and "</svg>" in svg:
        css = "    <style>\n" + "\n".join(f"      {r}" for r in rules) + "\n    </style>"
        svg = svg.replace("</svg>", f"{css}\n</svg>", 1)
    return svg
