"""Elem.kind -> ODF Frame/shape(s), built from the geometry-resolved IR.

Positions/sizes come from ``Elem.box`` (already cm, section-relative, from
render/odf/geometry.py). Content is built from the Elem's own structured
fields (inlines/items/rows/children) -- real ODF semantics (text:list,
table:table, per-run text:span), not HTML stripped to plain text.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Callable

from odfdo import Column, Frame, List as OdfList, ListItem, Paragraph, Row, Span, Table

from slidr.parser.ast import (
    CodeSpan, Emphasis, Image as ASTImage, LucideIcon, SoftBreak, Strikethrough,
    Strong, Text,
)
from slidr.render.ir import BoxGeometry, Elem, ResolvedStyle
from slidr.render.odf.styles import CM_PER_PX, StyleRegistry, px_to_cm, round_image_corners

AddFile = Callable[[str], str]


def render_elem(
    elem: Elem, reg: StyleRegistry, add_file: AddFile, source_dir: Path | None,
    global_tags: dict[str, ResolvedStyle],
) -> list[Any]:
    """Build every ODF shape for one Elem (and its children). []: not geometry-annotated."""
    if elem.box is None:
        return []
    fn = _RENDERERS.get(elem.kind, _render_text_like)
    shapes = fn(elem, reg, add_file, source_dir, global_tags)
    for child in elem.children:
        shapes.extend(render_elem(child, reg, add_file, source_dir, global_tags))
    return shapes


# ---------------------------------------------------------------------------
# geometry helpers
# ---------------------------------------------------------------------------


def _pos(box: BoxGeometry) -> tuple[str, str]:
    return (f"{box.x:.3f}cm", f"{box.y:.3f}cm")


def _size(box: BoxGeometry) -> tuple[str, str]:
    return (f"{max(box.w, 0.1):.3f}cm", f"{max(box.h, 0.1):.3f}cm")


def _apply_radius(frame: Frame, style: ResolvedStyle) -> None:
    if style.border_radius > 0:
        frame.set_attribute("draw:corner-radius", px_to_cm(style.border_radius))


# ---------------------------------------------------------------------------
# rich text (inline runs)
# ---------------------------------------------------------------------------


def _flatten_text(children: list) -> str:
    out = []
    for c in children:
        if isinstance(c, Text):
            out.append(c.content)
        elif isinstance(c, (Strong, Emphasis, Strikethrough)):
            out.append(_flatten_text(c.children))
        elif isinstance(c, CodeSpan):
            out.append(c.content)
    return "".join(out)


def _build_rich_paragraph(
    inlines: list, reg: StyleRegistry, base: ResolvedStyle,
    global_tags: dict[str, ResolvedStyle], para_style: str,
) -> Paragraph:
    p = Paragraph(style=para_style)
    for node in inlines:
        if isinstance(node, Text):
            p.append(node.content)
        elif isinstance(node, Strong):
            name = reg.run_style(base.fg, base.font_family, base.font_size_px, True, False)
            p.append(Span(_flatten_text(node.children), style=name))
        elif isinstance(node, Emphasis):
            name = reg.run_style(base.fg, base.font_family, base.font_size_px, False, True)
            p.append(Span(_flatten_text(node.children), style=name))
        elif isinstance(node, Strikethrough):
            p.append(_flatten_text(node.children))
        elif isinstance(node, CodeSpan):
            code = global_tags.get("code")
            family = code.font_family if code else base.font_family
            name = reg.run_style(base.fg, family, base.font_size_px, False, False, mono=True)
            p.append(Span(node.content, style=name))
        elif isinstance(node, ASTImage):
            p.append(f" [{node.alt or 'image'}] ")
        elif isinstance(node, SoftBreak):
            p.append(" ")
        elif isinstance(node, LucideIcon):
            pass  # vector icons have no ODF text equivalent; dropped, not faked
    return p


def _plain_paragraph(text: str, para_style: str) -> Paragraph:
    return Paragraph(text, style=para_style)


# ---------------------------------------------------------------------------
# renderers
# ---------------------------------------------------------------------------


def _render_text_like(
    elem: Elem, reg: StyleRegistry, add_file: AddFile, source_dir: Path | None,
    global_tags: dict[str, ResolvedStyle], *, border: bool = True,
) -> list[Any]:
    box = elem.box
    non_break = [n for n in elem.inlines if not isinstance(n, SoftBreak)]
    if non_break and all(isinstance(n, ASTImage) for n in non_break):
        # a paragraph whose entire content is image(s): render as picture(s),
        # not a text frame with "[alt]" placeholders.
        return _render_inline_images(non_break, box, add_file, source_dir)
    style = box.style
    para_style = reg.paragraph_style(style)
    content = (
        _build_rich_paragraph(elem.inlines, reg, style, global_tags, para_style)
        if elem.inlines else _plain_paragraph(_strip_html(elem.text or ""), para_style)
    )
    gfx = reg.graphic_style(style, fill=False, vertical_align="top", border=border)
    frame = Frame.text_frame(
        content, style=gfx, position=_pos(box), size=_size(box), anchor_type="page",
    )
    return [frame]


def _left_accent_bar(box: BoxGeometry, style: ResolvedStyle) -> Any | None:
    """CSS ``border-left`` accent (quote/notes callouts) has no ODF
    rectangle-outline equivalent -- a full ``draw:stroke`` paints all four
    sides. Draw it as a thin vertical line instead."""
    if not (style.border_color and style.border_width > 0):
        return None
    from odfdo import LineShape

    bar = LineShape(
        p1=(_pos(box)[0], _pos(box)[1]),
        p2=(_pos(box)[0], f"{box.y + box.h:.3f}cm"),
    )
    bar.set_attribute("svg:stroke-color", style.border_color)
    bar.set_attribute("svg:stroke-width", px_to_cm(style.border_width))
    return bar


def _render_quote(
    elem: Elem, reg: StyleRegistry, add_file: AddFile, source_dir: Path | None,
    global_tags: dict[str, ResolvedStyle],
) -> list[Any]:
    """Text frame plus a left accent bar (CSS ``border-left``, no ODF equivalent)."""
    shapes = _render_text_like(elem, reg, add_file, source_dir, global_tags, border=False)
    bar = _left_accent_bar(elem.box, elem.box.style)
    if bar is not None:
        shapes.insert(0, bar)
    return shapes


def _strip_html(text: str) -> str:
    """Card/table/notes text comes from the parser pre-expanded to inline
    HTML (bold, lucide icon SVG, etc. -- see plugins/fenced.py's
    _expand_markdown/_expand_icons). ODF cell/paragraph text is literal,
    not HTML: embedding it raw would print tag soup (confirmed: lucide
    icon SVGs showing as literal `<svg>...` text in table cells). Strip
    tags and decode entities (`&gt;`), then collapse whitespace: a
    multi-line SVG icon (newline after `<svg ...>`, one per `<path/>`)
    leaves literal `\\n` runs once its tags are gone, which `Paragraph`
    then turns into leading `text:line-break` elements pushing a card
    header down off the top of its box (confirmed: 5 icon newlines ->
    5 line breaks before the heading text)."""
    import html
    import re

    stripped = html.unescape(re.sub(r"<[^>]+>", "", text))
    return re.sub(r"\s+", " ", stripped).strip()


def _html_list_items(text: str) -> list[str] | None:
    """Card body lines are parser-pre-expanded HTML (plugins/fenced.py's
    _expand_markdown); a markdown bullet list inside a card body comes
    through as one ``<ul><li>...</li><li>...</li></ul>`` string -- blanket
    `_strip_html` on that concatenates every item with no separator
    (confirmed: "YOLO...Runs on NPUs..." ran together as one line).
    Returns each item's stripped text, or None if `text` isn't a list."""
    import re

    if not text.lstrip().startswith(("<ul", "<ol")):
        return None
    return [_strip_html(m) for m in re.findall(r"<li>(.*?)</li>", text, re.DOTALL)]


def _render_notes(
    elem: Elem, reg: StyleRegistry, add_file: AddFile, source_dir: Path | None,
    global_tags: dict[str, ResolvedStyle],
) -> list[Any]:
    box = elem.box
    style = box.style
    para_style = reg.paragraph_style(style)
    p = _plain_paragraph(_strip_html(elem.content or ""), para_style)
    gfx = reg.graphic_style(style, fill=True, vertical_align="middle", border=False)
    frame = Frame.text_frame(p, style=gfx, position=_pos(box), size=_size(box), anchor_type="page")
    _apply_radius(frame, style)
    bar = _left_accent_bar(box, style)
    return [bar, frame] if bar is not None else [frame]


def _highlighted_code_paragraph(
    code: str, language: str, style: ResolvedStyle, reg: StyleRegistry, para_style: str,
) -> Paragraph:
    """Per-token colored Spans via the same pygments lexer/style the HTML
    renderer uses (html.py's _highlight_code) -- previously code blocks were
    one flat mono Paragraph with no token coloring at all."""
    from pygments import lex
    from pygments.lexers import TextLexer, get_lexer_by_name
    from pygments.styles import get_style_by_name
    from pygments.util import ClassNotFound

    p = Paragraph(style=para_style)
    if not code:
        return p
    try:
        lexer = get_lexer_by_name(language) if language else TextLexer()
    except ClassNotFound:
        lexer = TextLexer()
    try:
        pyg_style = get_style_by_name(reg.pygments_style)
    except Exception:
        pyg_style = None
    for ttype, text in lex(code, lexer):
        if not text:
            continue
        color, bold, italic = style.fg, False, False
        if pyg_style is not None:
            tstyle = {}
            t = ttype
            while t is not None:
                try:
                    tstyle = pyg_style.style_for_token(t)
                    break
                except KeyError:
                    t = t.parent
            if tstyle.get("color"):
                color = f"#{tstyle['color']}"
            bold, italic = bool(tstyle.get("bold")), bool(tstyle.get("italic"))
        run = reg.run_style(color, style.font_family, style.font_size_px, bold, italic, mono=True)
        p.append(Span(text, style=run))
    return p


def _render_code(
    elem: Elem, reg: StyleRegistry, add_file: AddFile, source_dir: Path | None,
    global_tags: dict[str, ResolvedStyle],
) -> list[Any]:
    box = elem.box
    if elem.svg or elem.pdf:
        return _render_image_data(elem, box, add_file)
    style = box.style
    para_style = reg.paragraph_style(style, mono=True)
    p = _highlighted_code_paragraph(elem.content or "", elem.language, style, reg, para_style)
    gfx = reg.graphic_style(style, fill=True, vertical_align="top")
    frame = Frame.text_frame(p, style=gfx, position=_pos(box), size=_size(box), anchor_type="page")
    _apply_radius(frame, style)
    return [frame]


def _render_list(
    elem: Elem, reg: StyleRegistry, add_file: AddFile, source_dir: Path | None,
    global_tags: dict[str, ResolvedStyle],
) -> list[Any]:
    box = elem.box
    style = box.style
    li_style = box.substyles.get("li", style)
    para_style = reg.paragraph_style(li_style, margin_bottom_px=li_style.font_size_px * 0.4)
    marker_fg = box.substyles.get("li::marker", li_style).fg
    list_name = reg.list_style(marker_fg, li_style.font_family)
    odf_list = OdfList(style=list_name)
    inline_rows = elem.item_inlines or [[] for _ in elem.items]
    for row in inline_rows:
        p = (
            _build_rich_paragraph(row, reg, li_style, global_tags, para_style)
            if row else Paragraph(style=para_style)
        )
        odf_list.append_item(ListItem(p))
    gfx = reg.graphic_style(style, fill=False)
    frame = Frame.text_frame(odf_list, style=gfx, position=_pos(box), size=_size(box), anchor_type="page")
    return [frame]


def _render_table(
    elem: Elem, reg: StyleRegistry, add_file: AddFile, source_dir: Path | None,
    global_tags: dict[str, ResolvedStyle],
) -> list[Any]:
    box = elem.box
    style = box.style
    sub = box.substyles
    th_style = sub.get("th", style)
    td_odd = sub.get("tr:odd", style)
    td_even = sub.get("tr:even", style)

    ncols = len(elem.headers)
    nrows = len(elem.rows) + 1
    t = Table(f"SlidrTable_{elem.id}", width=max(ncols, 1), height=max(nrows, 1))

    # Without explicit column/row dims, Impress falls back to a fixed
    # per-column/-row default (bigger than the frame's own measured size),
    # rendering the table noticeably larger than the HTML -- size every
    # column/row to split the frame's own box evenly.
    if ncols:
        col_style = reg.table_column_style(box.w / ncols)
        for j in range(ncols):
            t.set_column(j, Column(style=col_style))
    if nrows:
        row_style = reg.table_row_style(box.h / nrows)
        for i in range(nrows):
            t.set_row(i, Row(style=row_style))

    header_cell = reg.table_cell_style(th_style.bg, th_style.border_color, th_style.border_width)
    header_run = reg.run_style(th_style.fg, th_style.font_family, th_style.font_size_px, True, False)
    for j, h in enumerate(elem.headers):
        text = _strip_html(h)
        t.set_value((j, 0), text)
        cell = t.get_cell((j, 0), clone=False)
        cell.set_attribute("table:style-name", header_cell)
        p = cell.get_element("text:p")
        if p is not None:
            p.clear()
            p.append(Span(text, style=header_run))

    for i, row in enumerate(elem.rows):
        row_fg_style = td_even if (i + 1) % 2 == 0 else td_odd
        cell_name = reg.table_cell_style(row_fg_style.bg, row_fg_style.border_color, row_fg_style.border_width)
        body_run = reg.run_style(
            row_fg_style.fg, row_fg_style.font_family, row_fg_style.font_size_px, False, False,
        )
        for j, cell_text in enumerate(row):
            text = _strip_html(cell_text)
            t.set_value((j, i + 1), text)
            cell = t.get_cell((j, i + 1), clone=False)
            cell.set_attribute("table:style-name", cell_name)
            p = cell.get_element("text:p")
            if p is not None:
                p.clear()
                p.append(Span(text, style=body_run))

    frame = Frame(
        name=f"table_frame_{elem.id}",
        position=_pos(box), size=_size(box), anchor_type="page",
    )
    frame.set_attribute("draw:fill", "none")
    frame.append(t)
    return [frame]


def _render_card(
    elem: Elem, reg: StyleRegistry, add_file: AddFile, source_dir: Path | None,
    global_tags: dict[str, ResolvedStyle],
) -> list[Any]:
    box = elem.box
    style = box.style
    header_style = box.substyles.get("h3", style)
    body_style = box.substyles.get("p", style)

    para_style = reg.paragraph_style(body_style)
    content: list[Any] = []
    icon_frame = None
    if elem.header:
        header_html = elem.header
        m = _ICON_SVG_RE.match(header_html.lstrip())
        if m:
            # Leading {icon:...} on a card header: no ODF inline-image-in-text
            # flow, so render it as its own small frame in the card's left
            # padding gutter (same convention as the bullet-list marker),
            # next to the header line, and drop it from the header text.
            header_html = header_html[header_html.index(m.group(0)) + len(m.group(0)):]
            icon_size = header_style.font_size_px * CM_PER_PX
            gutter_x = box.x + style.padding_left * CM_PER_PX - icon_size * 1.15
            icon_y = box.y + style.padding_top * CM_PER_PX
            icon_frame = _icon_frame(
                m.group(0), max(box.x, gutter_x), icon_y, icon_size, icon_size, add_file,
            )
        head_name = reg.run_style(
            header_style.fg, header_style.font_family, header_style.font_size_px,
            header_style.font_weight == "bold", False,
        )
        hp = Paragraph(style=para_style)
        hp.append(Span(_strip_html(header_html), style=head_name))
        content.append(hp)
    li_style = box.substyles.get("li", body_style)
    li_para_style = reg.paragraph_style(li_style, margin_bottom_px=li_style.font_size_px * 0.4)
    marker_fg = box.substyles.get("li::marker", li_style).fg
    list_name = reg.list_style(marker_fg, li_style.font_family)
    for line in elem.body:
        items = _html_list_items(line)
        if items is not None:
            odf_list = OdfList(style=list_name)
            for item in items:
                odf_list.append_item(ListItem(_plain_paragraph(item, li_para_style)))
            content.append(odf_list)
        else:
            content.append(_plain_paragraph(_strip_html(line), para_style))

    gfx = reg.graphic_style(style, fill=True, vertical_align="top")
    frame = Frame.text_frame(
        content or [Paragraph(style=para_style)],
        style=gfx, position=_pos(box), size=_size(box), anchor_type="page",
    )
    _apply_radius(frame, style)
    shapes = [frame]
    if icon_frame is not None:
        shapes.append(icon_frame)
    return shapes


def _render_grid(
    elem: Elem, reg: StyleRegistry, add_file: AddFile, source_dir: Path | None,
    global_tags: dict[str, ResolvedStyle],
) -> list[Any]:
    # Grid/row/col containers carry no visible paint of their own -- their
    # children (already geometry-annotated with their own absolute boxes)
    # render independently via render_elem's child recursion.
    return []


_render_row = _render_grid


def _render_speaker(
    elem: Elem, reg: StyleRegistry, add_file: AddFile, source_dir: Path | None,
    global_tags: dict[str, ResolvedStyle],
) -> list[Any]:
    box = elem.box
    style = box.style
    para_style = reg.paragraph_style(style)
    text = elem.text or ""
    links = [
        elem.attrs[key].replace("https://", "").replace("mailto:", "")
        for key in ("github", "twitter", "email", "linkedin", "website")
        if elem.attrs.get(key)
    ]
    if links:
        text = f"{text}\n{'  ·  '.join(links)}" if text else "  ·  ".join(links)
    p = Paragraph(text, style=para_style)
    gfx = reg.graphic_style(style, fill=False)
    frame = Frame.text_frame(p, style=gfx, position=_pos(box), size=_size(box), anchor_type="page")
    return [frame]


def _resolve_img_path(src: str, source_dir: Path | None) -> str | None:
    if src.startswith(("http://", "https://", "data:")):
        return None
    path = str((source_dir / src).resolve()) if source_dir else src
    return path if os.path.isfile(path) else None


def _normalize_svg_viewbox(svg: str) -> str:
    """Normalize a negative viewBox origin to 0,0, expanding dimensions."""
    import re

    m = re.search(r'viewBox="([\d.-]+)\s+([\d.-]+)\s+([\d.]+)\s+([\d.]+)"', svg)
    if not m:
        return svg
    x, y, w, h = float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4))
    if x >= 0 and y >= 0:
        return svg
    new_w, new_h = w + abs(x), h + abs(y)
    return svg.replace(m.group(0), f'viewBox="0 0 {new_w:g} {new_h:g}"', 1)


def _svg_dims(svg: str, max_w_cm: float) -> tuple[float, float]:
    import re

    vb = re.search(r'viewBox="[\d.-]+\s+[\d.-]+\s+([\d.]+)\s+([\d.]+)"', svg)
    if not vb:
        return (max_w_cm, max_w_cm * 9 / 16)
    vb_w, vb_h = float(vb.group(1)), float(vb.group(2))
    if vb_w <= 0:
        return (max_w_cm, max_w_cm * 9 / 16)
    w = min(max_w_cm, vb_w * 0.0353)
    return (w, w * (vb_h / vb_w))


_ICON_SVG_RE = re.compile(r"<svg\b[^>]*>.*?</svg>", re.DOTALL)


def _icon_frame(svg: str, x: float, y: float, w: float, h: float, add_file: AddFile) -> Any | None:
    """One lucide <svg> icon as a contain-fit image frame within (x, y, w, h).

    ``_svg_dims`` is tuned for diagrams (sizes from the viewBox's own unit
    count, e.g. a 0.0353cm/unit heuristic) -- a lucide icon's viewBox is a
    fixed ``0 0 24 24`` regardless of its requested on-slide size, so that
    heuristic forced every icon to the same ~0.85cm square no matter what
    box it was asked to fill (ignoring an explicit ``size=`` directive and
    overlapping adjacent text). Icons must instead respect the caller's
    box, fit to the icon's own aspect ratio (typically 1:1).

    render_icon's no-explicit-size path emits mismatched intrinsic dims
    (``width="24" height="1em"`` plus a ``style="height:1em;width:auto"``
    override, meant for inline HTML flow) -- confirmed empirically that
    LibreOffice's SVG import reads these as the icon's real aspect ratio
    instead of the viewBox, rendering a visibly non-square/compressed
    icon. Strip width/height/style from the <svg> tag itself so the
    viewBox is the only aspect-ratio signal left; Frame.image_frame's
    own declared cm size controls the final on-slide box regardless.
    """
    import tempfile

    svg = _normalize_svg_viewbox(svg)
    svg_tag_end = svg.index(">")
    svg_tag = svg[:svg_tag_end]
    for attr in ("width", "height", "style"):
        svg_tag = re.sub(rf'\s{attr}="[^"]*"', "", svg_tag, count=1)
    svg = svg_tag + svg[svg_tag_end:]
    vb = re.search(r'viewBox="[\d.-]+\s+[\d.-]+\s+([\d.]+)\s+([\d.]+)"', svg)
    aspect = (float(vb.group(1)) / float(vb.group(2))) if vb and float(vb.group(2)) > 0 else 1.0
    box_aspect = w / h if h > 0 else aspect
    iw, ih = (w, w / aspect) if aspect > box_aspect else (h * aspect, h)
    with tempfile.NamedTemporaryFile(suffix=".svg", mode="w", delete=False) as f:
        f.write(svg)
        tmp_path = f.name
    uri = add_file(tmp_path)
    os.unlink(tmp_path)
    ix, iy = x + (w - iw) / 2, y + (h - ih) / 2
    return Frame.image_frame(
        image=uri,
        size=(f"{iw:.3f}cm", f"{ih:.3f}cm"),
        position=(f"{ix:.3f}cm", f"{iy:.3f}cm"),
        anchor_type="page",
    )


def _render_arrow(
    elem: Elem, reg: StyleRegistry, add_file: AddFile, source_dir: Path | None,
    global_tags: dict[str, ResolvedStyle],
) -> list[Any]:
    """``::: arrow`` fenced block: a single centered lucide icon (default a
    plain arrow glyph), not text -- render as an image frame like any other
    inline icon, falling back to text if no icon markup is present."""
    box = elem.box
    m = _ICON_SVG_RE.search(elem.content or "")
    if not m:
        return _render_text_like(elem, reg, add_file, source_dir, global_tags)
    frame = _icon_frame(m.group(0), box.x, box.y, box.w, box.h, add_file)
    return [frame] if frame is not None else []


def _render_image_data(elem: Elem, box: BoxGeometry, add_file: AddFile) -> list[Any]:
    """Embed a mermaid/dot/seaborn diagram's rendered SVG (or mermaid's PDF
    fallback) directly as an ODF image -- LibreOffice embeds SVG/PDF images
    natively, no rasterization needed."""
    import tempfile

    size_cm = (box.w, box.h)
    tmp_path = None
    if elem.language == "mermaid" and elem.pdf:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(elem.pdf)
            tmp_path = f.name
    elif elem.svg:
        svg = _normalize_svg_viewbox(elem.svg)
        size_cm = _svg_dims(svg, box.w)
        with tempfile.NamedTemporaryFile(suffix=".svg", mode="w", delete=False) as f:
            f.write(svg)
            tmp_path = f.name
    if tmp_path is None:
        return [Frame.text_frame(
            Paragraph(f"[{elem.language or 'diagram'}]"),
            position=_pos(box), size=_size(box), anchor_type="page",
        )]
    uri = add_file(tmp_path)
    os.unlink(tmp_path)
    x, y = box.x + (box.w - size_cm[0]) / 2, box.y + (box.h - size_cm[1]) / 2
    frame = Frame.image_frame(
        image=uri,
        size=(f"{size_cm[0]:.3f}cm", f"{size_cm[1]:.3f}cm"),
        position=(f"{x:.3f}cm", f"{y:.3f}cm"),
        anchor_type="page",
    )
    return [frame]


def _render_inline_images(
    images: list, box: BoxGeometry, add_file: AddFile, source_dir: Path | None,
) -> list[Any]:
    """A paragraph whose entire content is one or more images, laid out
    centered side by side within the paragraph's own box."""
    resolved = [(img, _resolve_img_path(img.src, source_dir)) for img in images]
    resolved = [(img, p) for img, p in resolved if p]
    if not resolved:
        return []
    gap_cm = 0.3
    slot_w = (box.w - gap_cm * (len(resolved) - 1)) / len(resolved)
    frames = []
    x = box.x
    for img, path in resolved:
        w_cm, h_cm = _image_natural_size(path)
        if w_cm > slot_w:
            h_cm *= slot_w / w_cm
            w_cm = slot_w
        if h_cm > box.h:
            w_cm *= box.h / h_cm
            h_cm = box.h
        radius_cm = box.style.border_radius * CM_PER_PX
        uri = add_file(round_image_corners(path, radius_cm, w_cm))
        frame = Frame.image_frame(
            image=uri, text=img.title or "",
            size=(f"{w_cm:.3f}cm", f"{h_cm:.3f}cm"),
            position=(f"{x + (slot_w - w_cm) / 2:.3f}cm", f"{box.y + (box.h - h_cm) / 2:.3f}cm"),
            anchor_type="page",
        )
        if img.alt:
            frame.svg_description = img.alt
        frames.append(frame)
        x += slot_w + gap_cm
    return frames


def _image_natural_size(path: str) -> tuple[float, float]:
    try:
        from PIL import Image as PILImage

        with PILImage.open(path) as im:
            w_px, h_px = im.size
        return (w_px * 2.54 / 96, h_px * 2.54 / 96)
    except Exception:
        return (16.0, 9.0)


def _render_image(
    elem: Elem, reg: StyleRegistry, add_file: AddFile, source_dir: Path | None,
    global_tags: dict[str, ResolvedStyle],
) -> list[Any]:
    box = elem.box
    img = next((n for n in elem.inlines if isinstance(n, ASTImage)), None)
    src = img.src if img else elem.src
    path = _resolve_img_path(src, source_dir)
    if not path:
        return []
    radius_cm = box.style.border_radius * CM_PER_PX
    uri = add_file(round_image_corners(path, radius_cm, box.w))
    frame = Frame.image_frame(image=uri, position=_pos(box), size=_size(box), anchor_type="page")
    return [frame]


def _render_skip(
    elem: Elem, reg: StyleRegistry, add_file: AddFile, source_dir: Path | None,
    global_tags: dict[str, ResolvedStyle],
) -> list[Any]:
    """Elements with no ODF embedding (HTML5 <video>): render nothing, not a near-empty frame."""
    return []


_RENDERERS: dict[str, Any] = {
    "heading": _render_text_like,
    "text": _render_text_like,
    "kicker": _render_text_like,
    "subtitle": _render_text_like,
    "tiny": _render_text_like,
    "arrow": _render_arrow,
    "quote": _render_quote,
    "notes": _render_notes,
    "code": _render_code,
    "list": _render_list,
    "table": _render_table,
    "card": _render_card,
    "grid": _render_grid,
    "row": _render_row,
    "speaker": _render_speaker,
    "side-image": _render_image,
    "video": _render_skip,
}
