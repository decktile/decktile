"""HTML renderer for decktile."""

import os
import re
import subprocess
import tempfile
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from pygments import highlight
from pygments.lexers import get_lexer_by_name, TextLexer
from pygments.formatters import HtmlFormatter
from pygments.util import ClassNotFound

from decktile.parser.ast import Document
from decktile.render.ir import build_ir, SlideIR, Elem
from decktile.plugins.layouts import KNOWN_LAYOUTS

_pygments_style = "default"


_BRAND_ICON_SVGS = {
    "linkedin": (
        '<svg class="speaker-icon" xmlns="http://www.w3.org/2000/svg" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round" '
        'style="height:1em;width:auto;vertical-align:middle">'
        '<path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/>'
        '<rect width="4" height="12" x="2" y="9"/>'
        '<circle cx="4" cy="4" r="2"/></svg>'
    ),
}

TEMPLATE_DIR = Path(__file__).parent / "templates"
THEME_DIR = Path(__file__).parent.parent / "themes"
_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=False)


def default_theme() -> str:
    p = THEME_DIR / "default.css"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def load_theme(name: str) -> str:
    """Load a named theme CSS file. Falls back to default if not found."""
    p = THEME_DIR / f"{name}.css"
    return p.read_text(encoding="utf-8") if p.exists() else default_theme()


def base_css() -> str:
    p = TEMPLATE_DIR / "base.css"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def render(doc: Document, theme_css: str, assembled_css: str, dims: tuple[int, int], logo: str = "") -> str:
    from decktile.render.seaborn import set_palette

    global _pygments_style
    _pygments_style = doc.meta.pygments_style or "default"
    set_palette(doc.meta.seaborn_theme)

    ir_slides = build_ir(doc, base_css(), theme_css)
    return render_from_ir(ir_slides, doc, assembled_css, dims)


def render_from_ir(ir_slides: list[SlideIR], doc: Document, assembled_css: str,
                   dims: tuple[int, int]) -> str:
    """Render already-built IR slides to the full HTML page.

    Split out from render() so the ODP geometry pass can render the exact
    same IR (same data-decktile-id values) it will later annotate.
    """
    slides = []
    for i, slide in enumerate(ir_slides):
        children = _render_slide(slide)
        slides.append({
            "id": slide.id, "num": i + 1, "layout": slide.layout, "children": children,
            "notes": slide.notes, "footer": doc.meta.footer or "", "paginate": doc.meta.paginate or False,
            "variant": slide.variant or doc.meta.theme_variant,
            "transition": slide.transition or doc.meta.transition or "",
        })

    return _env.get_template("shell.html").render(
        title=doc.meta.title or "Presentation",
        slide_w=dims[0], slide_h=dims[1],
        css=assembled_css, slides=slides,
        variant=doc.meta.theme_variant or "light",
        autoplay=doc.meta.autoplay,
    )


def _render_slide(slide: SlideIR) -> str:
    elems = list(slide.elements)
    heading_html = ""
    if elems and elems[0].kind == "heading":
        heading_html = _render_elem(elems[0])
        elems = elems[1:]
    if elems and elems[0].kind == "subtitle":
        heading_html += "\n" + _render_elem(elems[0])
        elems = elems[1:]

    side_html = ""
    for e in list(elems):
        if e.kind == "side-image":
            side_html = f'<div class="side-image" data-decktile-id="{e.id}"><img src="{_escape(e.src)}" alt=""></div>'
            elems.remove(e)

    body_html = "\n".join(filter(None, (_render_elem(e) for e in elems)))
    if body_html.strip():
        heading_html += '\n<div class="slide-body">\n' + body_html + '\n</div>'
    if side_html:
        heading_html += side_html
    return heading_html or body_html


def _render_elem(e: Elem) -> str:
    sid = f' data-decktile-id="{e.id}"'
    if e.kind == "heading":
        tag = f"h{e.level}"
        return f"<{tag}{sid}>{e.content}</{tag}>"
    elif e.kind == "text":
        return f"<p{sid}>{e.content}</p>" if e.content else ""
    elif e.kind == "quote":
        return f'<div class="quote"{sid}>{e.content}</div>' if e.content else ""
    elif e.kind == "code":
        if e.language == "mermaid":
            return _render_mermaid(e.content, e.svg, sid)
        if e.language == "seaborn":
            return _render_seaborn_html(e.content, e.svg, sid)
        if e.language == "pdg":
            return _render_pdg_html(e.content, e.svg, sid, e.svg_live)
        return _highlight_code(e.content, e.language, sid)
    elif e.kind == "list":
        s = f"<ul{sid}>\n"
        for item in e.items:
            s += f"<li>{item}</li>\n"
        s += "</ul>"
        return s
    elif e.kind == "table":
        # cells are inline HTML rendered by the parser (markdown-it), like
        # card text -- escaping them again showed '&gt;' as '&amp;gt;'
        s = f"<table{sid}>\n<thead>\n<tr>"
        for h in e.headers:
            s += f"<th>{h}</th>"
        s += "</tr>\n</thead>\n<tbody>\n"
        for row in e.rows:
            s += "<tr>"
            for cell in row:
                s += f"<td>{cell}</td>"
            s += "</tr>\n"
        s += "</tbody>\n</table>"
        return s
    elif e.kind == "grid":
        if e.layout:
            cls = f"{e.layout}"
            if "compare" in cls:
                # children: col-left, arrow, col-right
                parts = "\n".join(filter(None, (_render_elem(c) for c in e.children)))
                return f'<div class="{cls}"{sid}>\n{parts}\n</div>'
            children = "\n".join(filter(None, (_render_elem(c) for c in e.children)))
            return f'<div class="{cls}"{sid}>\n{children}\n</div>'
        cols = e.cols or len(e.children) or 2
        style = f"grid-template-columns: repeat({cols}, 1fr); gap: 16px;"
        cls = "grid"
        if e.class_:
            cls += f" {e.class_}"
        children = "\n".join(filter(None, (_render_elem(c) for c in e.children)))
        return f'<div class="{cls}" style="{style}"{sid}>\n{children}\n</div>'
    elif e.kind == "card":
        cls = "card"
        if e.tag:
            cls += f" tag-{e.tag}"
        if e.class_:
            cls += f" {e.class_}"
        s = f'<div class="{cls}"{sid}>\n'
        if e.attrs.get("label"):
            s += f'<span class="timeline-label">{_escape(e.attrs["label"])}</span>\n'
        # header/body are inline HTML from fenced._expand_markdown (already
        # escaped by markdown-it): escaping again turned '>80%' into '&amp;gt;80%'
        if e.header:
            s += f"<h3>{e.header}</h3>\n"
        for line in e.body:
            if line.startswith("<ul") or line.startswith("<ol"):
                s += line + "\n"
            else:
                s += f"<p>{line}</p>\n"
        for child in e.children:
            s += _render_elem(child) + "\n"
        s += "</div>"
        return s
    elif e.kind == "arrow":
        return f'<div class="card-arrow"{sid}>{e.content}</div>'
    elif e.kind == "row":
        children = "\n".join(filter(None, (_render_elem(c) for c in e.children)))
        return f'<div class="row"{sid}>\n{children}\n</div>'
    elif e.kind == "notes":
        cls = "notes"
        if e.tag:
            cls += f" tag-{e.tag}"
        return f'<div class="{cls}"{sid}>{e.content}</div>'
    elif e.kind == "speaker":
        from decktile.plugins.lucide import render_icon
        name = e.attrs.get("name", e.content)
        role = e.attrs.get("role", "")
        text = f"{_escape(name)}<br><span class=\"role\">{_link_emails(_escape(role))}</span>" if role else _escape(name)
        links = []
        contact_icons = {"github": "git-fork", "twitter": "bird", "email": "mail", "website": "globe"}
        for key in ("github", "twitter", "email", "linkedin", "website"):
            val = e.attrs.get(key, "")
            if val:
                icon = contact_icons.get(key, "link")
                href = val if "://" in val else f"https://{val}" if key != "email" else f"mailto:{val}"
                label = val.replace("https://", "").replace("mailto:", "")
                svg = _BRAND_ICON_SVGS.get(key) or render_icon(icon, {"cls": "speaker-icon"})
                links.append(f'<a href="{_escape(href)}" target="_blank">{svg} {_escape(label)}</a>')
        if links:
            text += '<br><span class="speaker-links">' + "".join(links) + "</span>"
        label = e.attrs.get("contributor")
        if label:
            return f'<div class="speaker contributor"{sid}><span class="contributor-label">{_escape(label)}</span><br>{text}</div>'
        return f'<div class="speaker"{sid}>{text}</div>'
    elif e.kind in ("kicker", "subtitle", "tiny"):
        return f'<p class="{e.kind}"{sid}>{e.content}</p>'
    elif e.kind == "video":
        poster = _video_poster(e.src)
        return (f'<figure class="video"{sid}>'
                f'<video controls preload="metadata" src="{_escape(e.src)}" '
                f'poster="{_escape(poster)}"></video>'
                f'<img class="video-print" src="{_escape(poster)}" alt="">'
                f'</figure>')
    elif e.kind == "row-marker":
        return ""
    return ""


def _highlight_code(content: str, language: str, sid: str = "") -> str:
    try:
        lexer = get_lexer_by_name(language, stripall=True) if language else TextLexer()
    except ClassNotFound:
        lexer = TextLexer()
    formatter = HtmlFormatter(nowrap=True, style=_pygments_style)
    highlighted = highlight(content, lexer, formatter)
    cls = f' class="highlight language-{language}"' if language else ' class="highlight"'
    return f'<pre{cls}{sid}><code>{highlighted}</code></pre>'


def _pygments_css(style: str = "default") -> str:
    formatter = HtmlFormatter(style=style)
    css = formatter.get_style_defs('.slide .highlight')
    return f"\n/* ---- pygments ---- */\n{css}\n"


def _render_seaborn_html(content: str, svg: str = "", sid: str = "") -> str:
    if svg:
        return f'<div class="seaborn-plot"{sid}>\n{svg}\n</div>'
    return f'<pre class="seaborn-fallback"{sid}><code>{_escape(content)}</code></pre>'


def _render_mermaid(content: str, svg: str = "", sid: str = "") -> str:
    if svg:
        return f'<div class="mermaid"{sid}>\n{svg}\n</div>'
    return f'<pre class="mermaid-fallback"{sid}><code>{_escape(content)}</code></pre>'


_EMAIL_RX = re.compile(r"(?<![\w.@/:])([\w.+-]+@[\w-]+(?:\.[\w-]+)+)(?![\w@])")


def _link_emails(escaped: str) -> str:
    """Wrap bare email addresses in already-escaped text with mailto links."""
    return _EMAIL_RX.sub(r'<a href="mailto:\1">\1</a>', escaped)


def _render_pdg_html(content: str, svg: str = "", sid: str = "", live: str = "") -> str:
    if svg and live:
        # animated on screen, still frame in print/PDF (and for the ODP geometry pass)
        return (f'<div class="pdg-plot pdg-animated"{sid}>\n'
                f'<div class="pdg-live">{live}</div>\n<div class="pdg-still">{svg}</div>\n</div>')
    if svg:
        return f'<div class="pdg-plot"{sid}>\n{svg}\n</div>'
    return f'<pre class="pdg-fallback"{sid}><code>{_escape(content)}</code></pre>'


def _normalize_viewbox(svg: str) -> str:
    import re
    m = re.search(r'viewBox="([\d.-]+)\s+([\d.-]+)\s+([\d.]+)\s+([\d.]+)"', svg)
    if not m:
        return svg
    x, y, w, h = float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4))
    if x >= 0 and y >= 0:
        return svg
    new_w, new_h = w + abs(x), h + abs(y)
    return svg.replace(m.group(0), f'viewBox="0 0 {new_w:g} {new_h:g}"', 1)


def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _video_poster(src: str) -> str:
    """Poster/frame image for a video: same basename, .png extension."""
    return src.rsplit(".", 1)[0] + ".png"
