"""ODP renderer: thin orchestrator over geometry + styles + shapes.

build_ir -> annotate_geometry -> one DrawPage per slide, with its
background built from that slide's own resolved section style (gradient/
solid/bitmap-plus-overlay) -- no separate dark-mode code path, the
resolved style already reflects whatever ``data-theme`` the section had.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from odfdo import Document, DrawPage, Frame, Paragraph, PresentationNotes, RectangleShape

from slidr.parser.ast import Document as ASTDocument
from slidr.render.ir import ResolvedStyle, build_ir
from slidr.render.odf.geometry import annotate_geometry
from slidr.render.odf.shapes import render_elem
from slidr.render.odf.styles import StyleRegistry


def render(
    doc: ASTDocument,
    output_path: Path,
    base_css: str = "",
    theme_css: str = "",
    source_dir: Path | None = None,
) -> None:
    """Render Document AST to an ODP file.

    Page size is always derived from the deck's own px dimensions
    (``doc.meta.dimensions()``) via ``PX_TO_CM`` -- the same ratio
    geometry.py positions every frame with. A fixed/independent page size
    (the old default 28x15.75cm) would clip content: the geometry pass
    lays out frames assuming the page equals the content's real size.
    """
    from slidr.render.ir import assemble_css
    from slidr.render.odf.geometry import PX_TO_CM
    from slidr.render.seaborn import set_palette

    set_palette(doc.meta.seaborn_theme)
    dims = doc.meta.dimensions()
    page_width, page_height = dims[0] * PX_TO_CM, dims[1] * PX_TO_CM
    css = assemble_css(
        base_css, theme_css, dims, doc.meta.logo, doc.meta.watermark,
        doc.meta.pygments_style or "default", doc.meta.logo_dark,
    )

    ir_slides = build_ir(doc, base_css, theme_css)
    section_box, global_tags = annotate_geometry(ir_slides, doc, css, dims, source_dir)

    odp = Document("presentation")
    odp.body.clear()
    reg = StyleRegistry(odp, doc.meta.pygments_style or "default")

    def add_file(path: str) -> str:
        return odp.add_file(path)

    reg.ensure_page_layout(page_width, page_height)
    # Fallback only: base.css always defines `section::before { background:
    # var(--logo) ... }`, so the pseudo-element capture below is the normal
    # path. This covers a theme that doesn't set --logo at all.
    logo_path = _resolve_asset(doc.meta.logo, source_dir)
    logo_dark_path = _resolve_asset(doc.meta.logo_dark, source_dir) or logo_path

    for i, slide in enumerate(ir_slides):
        sb = section_box.get(slide.id)
        page = DrawPage(draw_id=slide.id, name=f"Slide {i + 1}")
        shapes: list[Any] = []

        if sb is not None:
            page.master_page = reg.master_for(sb.style, page_width, page_height, add_file)
            overlay = _overlay_shape(sb.style, reg, page_width, page_height)
            if overlay is not None:
                shapes.append(overlay)

        for e in slide.elements:
            shapes.extend(render_elem(e, reg, add_file, source_dir, global_tags))

        # Logo (section::before) / watermark (section::after): position,
        # size, and file come directly from weasyprint's own resolved box
        # for that pseudo-element -- exactly the HTML's CSS cascade,
        # including any `--logo: var(--logo-dark)` swap on dark/title
        # sections, with no separate Python-side light/dark selection.
        logo_shape = sb and sb.logo and _pseudo_image_frame(sb.logo, add_file)
        if logo_shape is not None:
            shapes.append(logo_shape)
        elif logo_path or logo_dark_path:
            slide_logo = logo_dark_path if slide.variant == "dark" else logo_path
            if slide_logo:
                shapes.append(_logo_frame(slide_logo, add_file, page_width, page_height))
        watermark_shape = sb and sb.watermark and _pseudo_image_frame(sb.watermark, add_file)
        if watermark_shape is not None:
            shapes.append(watermark_shape)
        footer_shape = sb and sb.footer and _text_pseudo_frame(sb.footer, reg)
        if footer_shape is not None:
            shapes.append(footer_shape)
        slide_num_shape = sb and sb.slide_num and _text_pseudo_frame(sb.slide_num, reg)
        if slide_num_shape is not None:
            shapes.append(slide_num_shape)

        # A bitmap-filled master page changes how LibreOffice resolves
        # z-order for un-indexed shapes (confirmed empirically: an
        # un-indexed overlay rect painted ABOVE a z-index=0 text frame --
        # the same shapes with no master page stacked correctly in
        # document order). Set an explicit, unique z-index per shape so
        # paint order can never depend on that default.
        for z, shape in enumerate(shapes):
            shape.set_attribute("draw:z-index", str(z))
            page.append(shape)

        if slide.notes:
            page.append(_notes_shape(slide.notes, page_width, page_height))

        odp.body.append(page)

    odp.save(str(output_path), pretty=True)


def _resolve_asset(src: str, source_dir: Path | None) -> str | None:
    if not src:
        return None
    path = str((source_dir / src).resolve()) if source_dir else src
    return path if os.path.isfile(path) else None


def _pseudo_image_frame(pseudo: Any, add_file: Any) -> Frame | None:
    """A section::before/::after box: exact position/size, and its own
    background-image url is the exact file the HTML used (already
    reflecting any CSS variable swap -- no separate Python-side selection).
    CSS uses ``background-size: contain`` (preserve the logo's own
    aspect, center within the box) -- Frame.image_frame stretches to the
    declared size, so fit-and-center within the CSS box using the file's
    real aspect ratio rather than distorting it to the box's aspect."""
    url = pseudo.style.bg_image_url
    if not url or not os.path.isfile(url):
        return None
    uri = add_file(url)
    box_w, box_h = pseudo.w, pseudo.h
    aspect = _image_aspect(url)
    box_aspect = box_w / box_h if box_h else (aspect or 1.0)
    if aspect and aspect > box_aspect:
        w, h = box_w, box_w / aspect
    elif aspect:
        w, h = box_h * aspect, box_h
    else:
        w, h = box_w, box_h
    x = pseudo.x + (box_w - w) / 2
    y = pseudo.y + (box_h - h) / 2
    return Frame.image_frame(
        image=uri,
        position=(f"{x:.3f}cm", f"{y:.3f}cm"),
        size=(f"{max(w, 0.01):.3f}cm", f"{max(h, 0.01):.3f}cm"),
        anchor_type="page",
    )


def _text_pseudo_frame(pseudo: Any, reg: StyleRegistry) -> Frame | None:
    """<footer>/.slide-num: a real DOM element injected by the HTML
    template (shell.html), not an AST node -- geometry.py captures it by
    tag/class against the enclosing section instead of by data-slidr-id.
    Position/size/background/color are exactly weasyprint's own resolved
    box for it (light-theme ``footer`` is a full-width bar via its own
    `left:0;right:0`, dark/title themes leave it text-only -- no
    Python-side special-casing, the CSS cascade already decided)."""
    if not pseudo.text:
        return None
    para_style = reg.paragraph_style(pseudo.style)
    gfx = reg.graphic_style(pseudo.style, fill=True, vertical_align="middle", border=False)
    p = Paragraph(pseudo.text, style=para_style)
    return Frame.text_frame(
        p, style=gfx,
        position=(f"{pseudo.x:.3f}cm", f"{pseudo.y:.3f}cm"),
        size=(f"{max(pseudo.w, 0.01):.3f}cm", f"{max(pseudo.h, 0.01):.3f}cm"),
        anchor_type="page",
    )


def _overlay_shape(
    style: ResolvedStyle, reg: StyleRegistry, page_w: float, page_h: float,
) -> Any | None:
    """Full-slide gradient/tint rect over a bitmap master background.

    Only needed when the section's background is a bitmap (photo) with a
    gradient/solid tint layered on top -- a pure gradient or solid fill
    (no bg_image_url) is already the master's own fill, no overlay needed.
    """
    if not (style.bg_image_url and os.path.isfile(style.bg_image_url)):
        return None
    name, _opacity = reg.overlay_style(style)
    return RectangleShape(
        style=name, position=("0cm", "0cm"),
        size=(f"{page_w:.3f}cm", f"{page_h:.3f}cm"), anchor_type="page",
    )


def _image_aspect(path: str) -> float | None:
    """width/height ratio of an image file. PIL has no SVG rasterizer at
    all (raises on open) -- parse viewBox/width/height from the SVG text
    directly rather than silently falling back to a guessed box (the old
    fixed 3.0x1.3cm fallback compressed any wide logo, confirmed: a real
    1305x298 SVG logo rendered squeezed into a 3.0/1.3=2.31 aspect box
    instead of its real 4.38 aspect)."""
    if path.lower().endswith(".svg"):
        import re

        svg = Path(path).read_text(errors="ignore")
        m = re.search(r'viewBox="[\d.-]+\s+[\d.-]+\s+([\d.]+)\s+([\d.]+)"', svg)
        if m:
            w, h = float(m.group(1)), float(m.group(2))
            return w / h if h else None
        m = re.search(r'width="([\d.]+)[a-z]*"', svg)
        m2 = re.search(r'height="([\d.]+)[a-z]*"', svg)
        if m and m2 and float(m2.group(1)):
            return float(m.group(1)) / float(m2.group(1))
        return None
    try:
        from PIL import Image

        with Image.open(path) as im:
            w_px, h_px = im.size
        return w_px / h_px if h_px else None
    except Exception:
        return None


def _logo_frame(logo_path: str, add_file: Any, page_w: float, page_h: float) -> Frame:
    target_w, target_h = 3.0, 1.3
    aspect = _image_aspect(logo_path)
    if aspect:
        target_h = target_w / aspect
    uri = add_file(logo_path)
    right_margin, top_margin = 1.0, 1.0
    return Frame.image_frame(
        image=uri, size=(f"{target_w:.2f}cm", f"{target_h:.2f}cm"),
        position=(f"{page_w - target_w - right_margin:.2f}cm", f"{top_margin:.2f}cm"),
        anchor_type="page",
    )


def _notes_shape(text: str, page_w: float, page_h: float) -> PresentationNotes:
    notes = PresentationNotes()
    frame = Frame.text_frame(
        Paragraph(text),
        position=("1.5cm", f"{page_h * 0.55:.2f}cm"),
        size=(f"{page_w - 3:.2f}cm", f"{page_h * 0.4:.2f}cm"),
        anchor_type="page", presentation_class="notes",
    )
    notes.append(frame)
    return notes
