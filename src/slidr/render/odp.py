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
    reg = StyleRegistry(odp)

    def add_file(path: str) -> str:
        return odp.add_file(path)

    reg.ensure_page_layout(page_width, page_height)
    logo_path = _resolve_asset(doc.meta.logo, source_dir)

    for i, slide in enumerate(ir_slides):
        sb = section_box.get(slide.id)
        page = DrawPage(draw_id=slide.id, name=f"Slide {i + 1}")

        if sb is not None:
            page.master_page = reg.master_for(sb.style, page_width, page_height, add_file)
            overlay = _overlay_shape(sb.style, reg, page_width, page_height)
            if overlay is not None:
                page.append(overlay)

        for e in slide.elements:
            for shape in render_elem(e, reg, add_file, source_dir, global_tags):
                page.append(shape)

        if logo_path:
            page.append(_logo_frame(logo_path, add_file, page_width, page_height))
        if slide.notes:
            page.append(_notes_shape(slide.notes, page_width, page_height))

        odp.body.append(page)

    odp.save(str(output_path), pretty=True)


def _resolve_asset(src: str, source_dir: Path | None) -> str | None:
    if not src:
        return None
    path = str((source_dir / src).resolve()) if source_dir else src
    return path if os.path.isfile(path) else None


def _overlay_shape(
    style: ResolvedStyle, reg: StyleRegistry, page_w: float, page_h: float,
) -> Any | None:
    """Full-slide gradient/tint rect over a bitmap master background.

    Only needed when the section's background is a bitmap (photo) with a
    gradient/solid tint layered on top -- a pure gradient or solid fill
    (no bg_image_url) is already the master's own fill, no overlay needed.
    """
    if not style.bg_image_url:
        return None
    name, _opacity = reg.overlay_style(style)
    return RectangleShape(
        style=name, position=("0cm", "0cm"),
        size=(f"{page_w:.3f}cm", f"{page_h:.3f}cm"), anchor_type="page",
    )


def _logo_frame(logo_path: str, add_file: Any, page_w: float, page_h: float) -> Frame:
    target_w, target_h = 3.0, 1.3
    try:
        from PIL import Image

        with Image.open(logo_path) as im:
            w_px, h_px = im.size
        if w_px:
            target_h = target_w * (h_px / w_px)
    except Exception:
        pass
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
