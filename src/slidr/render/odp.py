"""ODP renderer: thin orchestrator over geometry + styles + shapes.

build_ir -> annotate_geometry -> one DrawPage per slide, with its
background built from that slide's own resolved section style (gradient/
solid/bitmap-plus-overlay) -- no separate dark-mode code path, the
resolved style already reflects whatever ``data-theme`` the section had.
"""

from __future__ import annotations

import dataclasses
import os
from pathlib import Path
from typing import Any

from odfdo import Document, DrawPage, Frame, Paragraph, PresentationNotes, RectangleShape
from odfdo.element import Element

from slidr.parser.ast import Document as ASTDocument
from slidr.render.ir import ResolvedStyle, build_ir
from slidr.render.odf.geometry import annotate_geometry
from slidr.render.odf.shapes import render_elem
from slidr.render.odf.styles import StyleRegistry, downscale_image


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
        doc.meta.pygments_style or "default", doc.meta.logo_dark, doc.meta.background,
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
            master_name, is_new_master = reg.master_for(
                sb.style, page_width, page_height, add_file, footer=sb.footer,
            )
            page.master_page = master_name
            overlay = _overlay_shape(sb.style, reg, page_width, page_height)
            if overlay is not None:
                shapes.append(overlay)
            # Logo/watermark/footer-text/page-number are the same for every
            # slide sharing this master (same CSS rule, same fixed %-based
            # position) -- append them to the master page itself, exactly
            # once, instead of as a shape drawn on top of every single
            # slide. The footer *bar* fill is already baked into the
            # master's own background image (master_for); this adds the
            # bar's text, the page-number field, and the logo/watermark
            # images.
            #
            # Exception: a page whose background still needs a per-slide
            # overlay rect (a true multi-stop/angled gradient, e.g.
            # .layout-title, that can't be baked into the master --
            # reg.overlay_needed) -- master content always paints *beneath*
            # every per-slide shape in ODF, with no way to interleave by
            # z-index, so chrome placed on the master would be painted
            # over (dimmed/washed out) by that overlay on every single
            # slide using it. Keep chrome per-slide there instead, ordered
            # after the overlay so it paints on top of it, same as before
            # this master-chrome change.
            chrome_on_master = is_new_master and overlay is None
            chrome_per_slide = overlay is not None
            if chrome_on_master or chrome_per_slide:
                max_digits = len(str(len(ir_slides)))
                scope = "styles" if chrome_on_master else "content"
                chrome = _chrome_shapes(sb, reg, add_file, max_digits, scope=scope)
                if chrome_on_master:
                    mp = reg.master_page_element(master_name)
                    for shape in chrome:
                        mp.append(shape)
                else:
                    shapes.extend(chrome)


        # Fallback: a theme with no section::before CSS at all (sb.logo
        # is None, not just resolved-to-nothing) -- doc.meta.logo/
        # logo_dark directly, picked per slide.variant since it isn't
        # tied to any master.
        if (sb is None or sb.logo is None) and (logo_path or logo_dark_path):
            slide_logo = logo_dark_path if slide.variant == "dark" else logo_path
            if slide_logo:
                shapes.append(_logo_frame(slide_logo, add_file, page_width, page_height))

        for e in slide.elements:
            shapes.extend(render_elem(e, reg, add_file, source_dir, global_tags))

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
            page.append(_notes_shape(slide.notes, reg))

        odp.body.append(page)

    odp.save(str(output_path), pretty=True)


def _resolve_asset(src: str, source_dir: Path | None) -> str | None:
    if not src:
        return None
    path = str((source_dir / src).resolve()) if source_dir else src
    return path if os.path.isfile(path) else None


def _chrome_shapes(
    sb: Any, reg: StyleRegistry, add_file: Any, max_digits: int, *, scope: str,
) -> list[Any]:
    """footer-text, page-number field, logo, watermark -- the four shapes
    shared across every slide using one background style, built once and
    placed either on the master (``scope="styles"``) or, for an overlay-
    needing background, per-slide (``scope="content"``) by the caller."""
    shapes: list[Any] = []
    footer_shape = sb.footer and _text_pseudo_frame(
        sb.footer, reg, skip_fill=reg.footer_bar_baked(sb.style), scope=scope,
    )
    if footer_shape is not None:
        shapes.append(footer_shape)
    if sb.slide_num is not None:
        # Measured from the first slide using this master, which may well
        # be single-digit -- widen for the deck's actual max digit count
        # (right-aligned, so the extra width grows leftward and the
        # number stays flush with the original right edge), or a later
        # double-digit page wraps vertically inside the too-narrow box
        # instead of shrinking.
        digit_w = sb.slide_num.h * 0.6
        needed_w = max_digits * digit_w
        num_pseudo = sb.slide_num
        if needed_w > num_pseudo.w:
            num_pseudo = dataclasses.replace(
                num_pseudo,
                x=num_pseudo.x + num_pseudo.w - needed_w,
                w=needed_w,
                style=dataclasses.replace(num_pseudo.style, text_align="right"),
            )
        page_num_shape = _text_pseudo_frame(num_pseudo, reg, page_field=True, scope=scope)
        if page_num_shape is not None:
            shapes.append(page_num_shape)
    # Logo (section::before) / watermark (section::after): position,
    # size, and file come directly from weasyprint's own resolved box for
    # that pseudo-element -- exactly the HTML's CSS cascade, including
    # any `--logo: var(--logo-dark)` swap on dark/title sections, with no
    # separate Python-side light/dark selection. sb.logo being present
    # but resolving to no image (`background-image: none`) is the
    # cascade explicitly deciding no logo on this variant -- not a
    # missing-CSS case, so no fallback there.
    if sb.logo is not None:
        logo_shape = _pseudo_image_frame(sb.logo, add_file)
        if logo_shape is not None:
            shapes.append(logo_shape)
    watermark_shape = sb.watermark and _pseudo_image_frame(sb.watermark, add_file)
    if watermark_shape is not None:
        shapes.append(watermark_shape)
    return shapes


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
    uri = add_file(downscale_image(url, pseudo.w, pseudo.h))
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


def _text_pseudo_frame(
    pseudo: Any, reg: StyleRegistry, *, skip_fill: bool = False, page_field: bool = False,
    scope: str = "styles",
) -> Frame | None:
    """<footer>/.slide-num: a real DOM element injected by the HTML
    template (shell.html), not an AST node -- geometry.py captures it by
    tag/class against the enclosing section instead of by data-slidr-id.
    Position/size/background/color are exactly weasyprint's own resolved
    box for it (light-theme ``footer`` is a full-width bar via its own
    `left:0;right:0`, dark/title themes leave it text-only -- no
    Python-side special-casing, the CSS cascade already decided).
    ``skip_fill``: the bar is already baked into the master's own bitmap
    fill (``reg.footer_bar_baked``) -- painting it again here would
    double it (and need its own, harder-to-get-right z-order against the
    watermark/logo shapes that sit inside it).
    ``page_field``: ``.slide-num``'s text is the slide's index at build
    time, baked as a literal string -- inserting, deleting, or reordering
    a slide afterward in Impress leaves every later page number wrong.
    Use a live ``text:page-number`` field instead (``text:select-page=
    "current"``, cached display value = the build-time number), which
    Impress recomputes from actual page position regardless of later
    edits.
    ``scope``: this frame may land on the master page (``"styles"``) or,
    for an overlay-needing background, on the slide itself (``"content"``)
    -- Impress resolves text/paragraph styles from whichever XML part the
    *shape* lives in, not the document as a whole, so the two placements
    need oppositely-scoped styles or the font/color silently falls back
    to a default serif/black.
    """
    if not pseudo.text:
        return None
    para_style = reg.paragraph_style(pseudo.style, scope=scope)
    gfx = reg.graphic_style(
        pseudo.style, fill=not skip_fill and pseudo.style.bg_alpha > 0,
        vertical_align="middle", border=False,
    )
    if page_field:
        p = Paragraph(style=para_style)
        field = Element.from_tag("text:page-number")
        field.set_attribute("text:select-page", "current")
        field.text = pseudo.text
        p.append(field)
    else:
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

    Needed only for a true multi-stop/angled gradient over a photo
    (``.layout-title``'s directional fade) -- a uniform tint (every
    other section's light/dark overlay) is baked directly into the
    master's own bitmap fill by ``master_for``, one master per (image,
    tint) switched via ``master_page`` instead of a per-slide alpha-
    composited shape on top of one shared bitmap. ``reg.overlay_needed``
    is the single source of truth (not re-derived here independently):
    it reflects whether that baking actually succeeded, not just
    whether it was attempted, so a PIL-missing environment can't end up
    with neither the baked tint nor this overlay. A pure gradient/solid
    fill (no bg_image_url) is already the master's own fill either way.
    """
    if not reg.overlay_needed(style):
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


def _notes_shape(text: str, reg: StyleRegistry) -> PresentationNotes:
    """The notes page is a separate, independently-sized portrait page --
    not derived from the slide's own landscape page dimensions. Geometry
    matched against a LibreOffice-authored reference (python-pptx deck
    with real notes, converted via soffice --convert-to odp): the
    master's own "Blank-notes" placeholder sits at (2.1cm, 14.107cm)
    sized 16.799cm x 13.364cm. Using the slide's own (wider, landscape)
    page width/height here clipped every notes line off the right edge
    of the portrait notes page."""
    notes = PresentationNotes()
    # One Paragraph per source line -- a plain Paragraph("a\nb") renders
    # "a" and "b" run together (ODF text:p ignores embedded \n; it needs
    # explicit text:line-break or paragraph breaks), which silently
    # collapsed multi-line comments and bulleted notes onto one line.
    paragraphs = [Paragraph(line) for line in text.split("\n")]
    frame = Frame.text_frame(
        paragraphs,
        position=("2.1cm", "14.107cm"),
        size=("16.799cm", "13.364cm"),
        anchor_type="page", presentation_class="notes",
        presentation_style=reg.notes_style(),
    )
    notes.append(frame)
    return notes
