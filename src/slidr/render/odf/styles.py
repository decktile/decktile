"""ODF Style registries built from resolved (weasyprint-derived) styles.

Every registry dedups by a hashable key derived from ResolvedStyle so two
elements with identical computed style share one odfdo Style object. Each
``*_style``/``*_name`` method inserts into the document immediately (no
deferred batch-insert pass) -- odfdo dedups by name internally and this
keeps the registration/use sites next to each other.
"""

from __future__ import annotations

import math
import functools
import os
import tempfile

from dataclasses import dataclass
from itertools import count
from typing import Callable

from odfdo import Document, DrawFillImage, Style, StyleMasterPage, StylePageLayout
from odfdo.element import Element

from slidr.render.ir import ResolvedStyle

PX_TO_PT = 0.75          # CSS px (96dpi) -> pt (72dpi)
CM_PER_PX = 2.54 / 96.0


def css_angle_to_odf(css_deg: float, width_cm: float, height_cm: float) -> float:
    """CSS gradient angle -> ODF draw:angle (plain degrees).

    ODF measures 0deg = top-to-bottom, rotating counter-clockwise (opposite
    sense from CSS) -- nominal angle is ``(180 - css) % 360``. But ODF's
    linear gradient line is defined relative to the shape's own bounding
    box, so a non-square shape stretches the visual angle; compensate via
    atan2(sin(t)*W, cos(t)*H). Verified empirically against weasyprint's
    render at a real 16:9 slide (css 135deg -> odf ~60.7deg, confirmed
    pixel-for-pixel via corner-color sampling through soffice).
    """
    if width_cm <= 0 or height_cm <= 0:
        width_cm = height_cm = 1.0
    nominal = math.radians((180 - css_deg) % 360)
    odf_deg = math.degrees(math.atan2(math.sin(nominal) * width_cm, math.cos(nominal) * height_cm))
    return odf_deg % 360


def px_to_pt(px: float) -> str:
    return f"{px * PX_TO_PT:.2f}pt"


def px_to_cm(px: float) -> str:
    return f"{px * CM_PER_PX:.3f}cm"


def downscale_image(path: str, width_cm: float, height_cm: float) -> str:
    """Downscale an oversized bitmap before embedding, to 2x the target's
    own pixel size -- used for both per-page master backgrounds (one
    style, but Impress recomposites it fresh for every page using it --
    see ``StyleRegistry._prepare_bg_image``) and per-slide logo/watermark
    frames (one frame per slide, each independently decoded/resampled by
    the same mechanism; a wide source watermark photo turned a one-time
    decode into a cost repeated on every slide carrying it). Preserves
    alpha -- a logo/watermark PNG's transparency must survive, unlike an
    opaque full-bleed background photo. Skipped entirely if already
    smaller than the target. Memoized: the same source+box recurring on
    every slide (a deck-wide logo/watermark) would otherwise re-decode
    and re-embed as a distinct Pictures/ entry on every call -- add_file
    dedups by path, and a fresh mkstemp path every call defeats that.
    """
    return _downscale_image_cached(path, round(width_cm, 2), round(height_cm, 2))


@functools.lru_cache(maxsize=256)
def _downscale_image_cached(path: str, width_cm: float, height_cm: float) -> str:
    try:
        from PIL import Image
    except ImportError:
        return path
    target_w = max(1, round(width_cm / CM_PER_PX * 2))
    target_h = max(1, round(height_cm / CM_PER_PX * 2))
    try:
        with Image.open(path) as im:
            if im.width <= target_w and im.height <= target_h:
                return path
            scale = min(target_w / im.width, target_h / im.height)
            size = (max(1, round(im.width * scale)), max(1, round(im.height * scale)))
            mode = "RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB"
            resized = im.convert(mode).resize(size, Image.LANCZOS)
            fd, out_path = tempfile.mkstemp(suffix=".png")
            os.close(fd)
            resized.save(out_path)
            return out_path
    except Exception:
        return path


def is_uniform_tint(gradient: list[tuple[float, str, float]] | None) -> bool:
    """A CSS ``background-image`` gradient layer that is the *same* color
    and alpha at every stop (``linear-gradient(var(--bg-overlay), var(--bg-overlay))``,
    used by every non-title section in this deck's themes) is really a flat
    tint, not a gradient -- it can be pre-composited into one flattened
    master-page fill per (image, tint) combination and switched per slide
    via ``master_page``, instead of a per-slide alpha-composited overlay
    shape on top of one shared bitmap master. A true multi-stop/angled
    gradient (``.layout-title``'s directional fade) still needs the
    per-slide overlay -- it can't be expressed as a single flat color.
    """
    if not gradient:
        return False
    first_hex, first_alpha = gradient[0][1], gradient[0][2]
    return all(g[1] == first_hex and abs(g[2] - first_alpha) < 0.01 for g in gradient)


def _bitmap_tint_key(style: ResolvedStyle) -> tuple | None:
    """The (image, tint) master key, or None if this style's background
    doesn't qualify for a baked-tint master (no image, or a true multi-
    stop/angled gradient like ``.layout-title``'s that can't be
    flattened to one tint). Single source shared by ``master_for`` and
    ``overlay_needed``/``footer_bar_baked`` so they can't drift."""
    if not (style.bg_image_url and os.path.isfile(style.bg_image_url)):
        return None
    if not is_uniform_tint(style.bg_gradient):
        return None
    tint_hex, tint_alpha = style.bg_gradient[0][1], round(style.bg_gradient[0][2], 3)
    return ("bitmap-tinted", style.bg_image_url, tint_hex, tint_alpha)


def _master_label(key: tuple, tint_hex: str | None) -> str:
    """A descriptive master-page name (shows in Impress's layout panel as
    e.g. "SlidrLight1") instead of a bare counter -- the whole point of
    baking tints into distinct masters is a layout switched per slide,
    which should read as one in the UI, not just in the XML."""
    if key[0] == "bitmap-tinted" and tint_hex:
        r, g, b = (int(tint_hex[i:i + 2], 16) for i in (1, 3, 5))
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return "Light" if luminance > 0.5 else "Dark"
    if key[0] in ("bitmap", "gradient"):
        return "Gradient"
    return "Solid"


@dataclass(frozen=True)
class _TextKey:
    fg: str
    font_family: str
    font_size_px: float
    weight: str
    italic: bool
    text_align: str
    margin_bottom_px: float = 0.0

@dataclass(frozen=True)
class _GraphicKey:
    bg: str
    border_color: str
    border_width_px: float
    border_radius_px: float
    text_align: str
    vertical_align: str
    padding: tuple[float, float, float, float]


class StyleRegistry:
    """Owns every ODF style created for one ODP document."""

    def __init__(self, document: Document, pygments_style: str = "default") -> None:
        self.pygments_style = pygments_style
        self._doc = document
        self._fonts: set[str] = set()
        self._paragraph: dict[_TextKey, str] = {}
        self._run: dict[_TextKey, str] = {}
        self._graphic: dict[_GraphicKey, str] = {}
        self._table_cells: dict[tuple, str] = {}
        self._table_dims: dict[tuple, str] = {}
        self._list_styles: dict[tuple, str] = {}
        self._overlay: dict[tuple, tuple[str, str | None]] = {}
        self._gradients: dict[tuple, str] = {}
        self._opacities: dict[tuple, str] = {}
        self._masters: dict[tuple, str] = {}
        self._tint_baked_keys: set[tuple] = set()
        self._footer_baked: dict[tuple, bool] = {}
        self._label_counters: dict[str, int] = {}
        self._pil_ok: bool | None = None
        self._page_layout_name: str | None = None
        self._page_w: float = 0.0
        self._page_h: float = 0.0
        self._counter = count(1)

    # ---- fonts ----

    def ensure_font(self, family: str, mono: bool = False) -> None:
        if not family or family in self._fonts:
            return
        self._fonts.add(family)
        face = Style(
            "font-face", font_name=family, font_family=family,
            font_family_generic="modern" if mono else "swiss",
            font_pitch="fixed" if mono else "variable",
        )
        self._doc.insert_style(face)
        self._doc.insert_style(face.clone, default=True)

    # ---- text (paragraph default + inline run) styles ----

    def paragraph_style(self, style: ResolvedStyle, *, mono: bool = False,
                        margin_bottom_px: float = 0.0) -> str:
        """Automatic (content.xml) style -- verified empirically: Impress's
        draw:text-box only resolves text:p/text:span against automatic
        styles, silently ignoring an identical common (styles.xml) style
        (same family of pitfall as the table-cell/master-background ones)."""
        key = _TextKey(style.fg, style.font_family, style.font_size_px,
                      style.font_weight, style.font_italic, style.text_align,
                      round(margin_bottom_px, 1))
        cached = self._paragraph.get(key)
        if cached:
            return cached
        self.ensure_font(style.font_family, mono=mono)
        name = f"SlidrP{next(self._counter)}"
        s = Style("paragraph", name=name)
        s.set_properties(area="paragraph", align=style.text_align)
        if margin_bottom_px:
            s.set_properties({"fo:margin-bottom": px_to_cm(margin_bottom_px)}, area="paragraph")
        s.set_properties(
            area="text", color=style.fg, font=style.font_family,
            font_family=style.font_family, family_generic="modern" if mono else "swiss",
            size=px_to_pt(style.font_size_px), weight=style.font_weight,
            font_style="italic" if style.font_italic else "normal",
        )
        self._doc.insert_style(s, automatic=True)
        self._paragraph[key] = name
        return name

    def run_style(self, fg: str, font_family: str, font_size_px: float,
                 bold: bool, italic: bool, *, mono: bool = False) -> str:
        key = _TextKey(fg, font_family, font_size_px,
                      "bold" if bold else "normal", italic, "")
        cached = self._run.get(key)
        if cached:
            return cached
        self.ensure_font(font_family, mono=mono)
        name = f"SlidrT{next(self._counter)}"
        s = Style("text", name=name, bold=bold, italic=italic)
        s.set_properties(
            area="text", color=fg, font=font_family, font_family=font_family,
            family_generic="modern" if mono else "swiss", size=px_to_pt(font_size_px),
        )
        self._doc.insert_style(s, automatic=True)
        self._run[key] = name
        return name

    def list_style(self, color: str, font_family: str) -> str:
        """Bullet list style matching base.css's ``ul { list-style: var(--list-style) }``
        (bullet char U+25B8) and ``li::marker { color: var(--color-accent) }``.
        Impress ignores ``text:list-level-style-bullet/@text:style-name`` for
        the bullet glyph's color (verified empirically against real output);
        an inline ``style:text-properties`` child is what it actually honors.
        """
        key = (color, font_family)
        cached = self._list_styles.get(key)
        if cached:
            return cached
        self.ensure_font(font_family)
        name = f"SlidrL{next(self._counter)}"
        s = Style("list", name=name)
        level = s.set_level_style(1, bullet_char="\u25b8")
        if level is not None:
            props = Element.from_tag("style:list-level-properties")
            props.set_attribute("text:space-before", "0cm")
            props.set_attribute("text:min-label-width", "0.5cm")
            level.append(props)
            tprops = Element.from_tag("style:text-properties")
            tprops.set_attribute("fo:color", color)
            tprops.set_attribute("style:font-name", font_family)
            level.append(tprops)
        self._doc.insert_style(s, automatic=True)
        self._list_styles[key] = name
        return name

    def table_cell_style(self, bg: str, border_color: str, border_width_px: float) -> str:
        """Impress tables are *draw* tables, not spreadsheet tables: a cell's
        fill is read from style:graphic-properties (draw:fill/draw:fill-color),
        not style:table-cell-properties (fo:background-color) -- verified
        against real LibreOffice output; the Writer/Calc-style property is
        silently ignored by Impress and the default blue banding shows
        through instead. Must be an automatic (content.xml) style; odfdo's
        get_style('table-cell', ...) only resolves there for Impress tables.
        """
        key = (bg, border_color, round(border_width_px, 1))
        cached = self._table_cells.get(key)
        if cached:
            return cached
        name = f"SlidrTC{next(self._counter)}"
        s = Style("table-cell", name=name)
        s.set_properties(
            {"draw:fill": "solid" if bg else "none", "draw:fill-color": bg or "#ffffff",
             "draw:textarea-vertical-align": "middle"},
            area="graphic",
        )
        s.set_properties(
            {"fo:border": f"{px_to_pt(border_width_px) if border_width_px else '0.5pt'} "
                          f"solid {border_color or '#cccccc'}"},
            area="paragraph",
        )
        self._doc.insert_style(s, automatic=True)
        self._table_cells[key] = name
        return name

    def table_column_style(self, width_cm: float) -> str:
        """Explicit column width -- without it Impress tables fall back to
        a fixed per-column default, ignoring the frame's own measured
        width/font sizes and rendering noticeably larger than the HTML.
        ``width``/``height`` for table-column/table-row only map to
        ``style:column-width``/``style:row-height`` as ``Style()``
        constructor kwargs (``Style.__init__``), not via a later
        ``set_properties()`` call -- verified against odfdo source.
        """
        key = round(width_cm, 3)
        cached = self._table_dims.get(("col", key))
        if cached:
            return cached
        name = f"SlidrTCW{next(self._counter)}"
        s = Style("table-column", name=name, width=f"{width_cm:.3f}cm")
        self._doc.insert_style(s, automatic=True)
        self._table_dims[("col", key)] = name
        return name

    def table_row_style(self, height_cm: float) -> str:
        key = round(height_cm, 3)
        cached = self._table_dims.get(("row", key))
        if cached:
            return cached
        name = f"SlidrTRH{next(self._counter)}"
        s = Style("table-row", name=name, height=f"{height_cm:.3f}cm")
        self._doc.insert_style(s, automatic=True)
        self._table_dims[("row", key)] = name
        return name

    # ---- graphic (frame fill/border/padding) ----

    def graphic_style(self, style: ResolvedStyle, *, fill: bool = True,
                      vertical_align: str = "top", border: bool = True) -> str:
        padding = (style.padding_top, style.padding_right, style.padding_bottom, style.padding_left)
        key = _GraphicKey(
            style.bg if fill else "", style.border_color if border else "",
            style.border_width if border else 0.0,
            style.border_radius, style.text_align, vertical_align, padding,
        )
        cached = self._graphic.get(key)
        if cached:
            return cached
        name = f"SlidrG{next(self._counter)}"
        s = Style("graphic", name=name)
        props: dict[str, str] = {
            "draw:textarea-vertical-align": vertical_align,
            # LibreOffice's text engine can wrap a few percent wider than
            # weasyprint measured (font substitution/metrics differences);
            # auto-grow-height let that push the frame past its measured
            # box and collide with the next sibling (fixed-position frames
            # don't reflow). shrink-to-fit keeps every frame at its
            # weasyprint-measured size and scales text down instead,
            # verified empirically to eliminate the overlap.
            "draw:auto-grow-height": "false",
            "style:shrink-to-fit": "true",
            "fo:padding-top": px_to_cm(style.padding_top),
            "fo:padding-right": px_to_cm(style.padding_right),
            "fo:padding-bottom": px_to_cm(style.padding_bottom),
            "fo:padding-left": px_to_cm(style.padding_left),
        }
        if fill and style.bg:
            props["draw:fill"] = "solid"
            props["draw:fill-color"] = style.bg
        else:
            props["draw:fill"] = "none"
        if border and style.border_color and style.border_width > 0:
            props["draw:stroke"] = "solid"
            props["svg:stroke-color"] = style.border_color
            props["svg:stroke-width"] = px_to_cm(style.border_width)
        else:
            props["draw:stroke"] = "none"
        # draw:corner-radius is a draw:rect/frame element attribute in ODF,
        # not a style:graphic-properties one (odfdo's whitelist agrees --
        # confirmed it silently drops it here); shapes.py sets it directly
        # on the Frame/RectangleShape it builds, keyed off style.border_radius.
        s.set_properties(props, area="graphic")
        s.set_properties(area="paragraph", align=style.text_align)
        self._doc.insert_style(s)
        self._graphic[key] = name
        return name

    # ---- family-less raw styles: draw:gradient / draw:opacity ----
    # odfdo has no Style class for either family (Style("gradient"/"opacity", ...)
    # raises "Unknown family value") -- both are built as raw XML and appended
    # directly to office:styles, same escape hatch insert_style(str) documents.

    def gradient_name(self, stops: list[tuple[float, str, float]], angle_deg: float) -> str:
        key = (tuple(stops), round(angle_deg))
        cached = self._gradients.get(key)
        if cached:
            return cached
        name = f"SlidrGrad{next(self._counter)}"
        start_hex, end_hex = stops[0][1], stops[-1][1]
        odf_deg = css_angle_to_odf(angle_deg, self._page_w, self._page_h)
        # draw:start-color/end-color are the base-ODF 2-stop fallback;
        # loext:gradient-stop children (a LibreOffice extension, verified
        # rendering every stop) carry the full N-stop gradient so a middle
        # stop's hue (e.g. kcd_vietnam's #7a0504 red) isn't lost.
        stop_xml = "".join(
            f'<loext:gradient-stop svg:offset="{offset:.4f}" '
            f'loext:color-type="rgb" loext:color-value="{hex_color}"/>'
            for offset, hex_color, _alpha in stops
        )
        el = Element.from_tag(
            f'<draw:gradient draw:name="{name}" draw:style="linear" '
            f'draw:angle="{odf_deg:.0f}deg" draw:start-color="{start_hex}" '
            f'draw:end-color="{end_hex}" draw:start-intensity="100%" '
            f'draw:end-intensity="100%" draw:border="0%">{stop_xml}</draw:gradient>'
        )
        self._doc.styles.get_element("office:styles").append(el)
        self._gradients[key] = name
        return name

    def opacity_name(self, stops: list[tuple[float, str, float]], angle_deg: float) -> str | None:
        """Per-axis opacity gradient name, or None if fully opaque throughout.

        ``draw:opacity``'s ``draw:start``/``draw:end`` are plain opacity
        percentages (0%=fully transparent, 100%=fully opaque) -- confirmed
        empirically against the installed LibreOffice via a solid-color
        corner-sample test (0/25/75/100% inputs produced exactly that much
        of the foreground color blended in): the direct CSS-alpha sense,
        not inverted. A flat run of equal alphas (common: kubecon_japan's
        gradient is 0.85 throughout) is approximated with ``draw:border``
        holding the start value before the real fade.
        """
        alphas = [a for _, _, a in stops]
        if all(a >= 0.999 for a in alphas):
            return None
        key = (tuple(stops), round(angle_deg))
        cached = self._opacities.get(key)
        if cached:
            return cached
        start_alpha, end_alpha = alphas[0], alphas[-1]
        border_pct = 0.0
        for offset, _, a in stops[1:-1]:
            if abs(a - start_alpha) < 0.05:
                border_pct = offset * 100
        name = f"SlidrOpac{next(self._counter)}"
        odf_deg = css_angle_to_odf(angle_deg, self._page_w, self._page_h)
        el = Element.from_tag(
            f'<draw:opacity draw:name="{name}" draw:style="linear" '
            f'draw:angle="{odf_deg:.0f}deg" '
            f'draw:start="{start_alpha * 100:.0f}%" '
            f'draw:end="{end_alpha * 100:.0f}%" '
            f'draw:border="{border_pct:.0f}%"/>'
        )
        self._doc.styles.get_element("office:styles").append(el)
        self._opacities[key] = name
        return name

    def overlay_style(self, style: ResolvedStyle) -> tuple[str, str | None]:
        """Graphic style for a full-slide overlay rect (gradient-over-image case)."""
        if style.bg_gradient:
            grad_name = self.gradient_name(style.bg_gradient, style.bg_angle_deg)
            fill_props = {"draw:fill": "gradient", "draw:fill-gradient-name": grad_name}
            opacity = self.opacity_name(style.bg_gradient, style.bg_angle_deg)
        else:
            fill_props = {"draw:fill": "solid", "draw:fill-color": style.bg}
            opacity = None
        key = ("overlay", tuple(sorted(fill_props.items())), opacity)
        cached = self._overlay.get(key)
        if cached:
            return cached
        name = f"SlidrOverlay{next(self._counter)}"
        s = Style("graphic", name=name)
        props = dict(fill_props)
        props["draw:stroke"] = "none"
        if opacity:
            props["draw:opacity-name"] = opacity
        s.set_properties(props, area="graphic")
        self._doc.insert_style(s)
        self._overlay[key] = (name, opacity)
        return name, opacity

    # ---- page layout + master page (slide/master background) ----

    def ensure_page_layout(self, width_cm: float, height_cm: float) -> str:
        self._page_w, self._page_h = width_cm, height_cm
        if self._page_layout_name:
            return self._page_layout_name
        name = "SlidrPageLayout"
        pl = StylePageLayout(name=name)
        pl.set_properties(
            page_width=f"{width_cm:.3f}cm", page_height=f"{height_cm:.3f}cm",
            margin_top="0cm", margin_bottom="0cm", margin_left="0cm", margin_right="0cm",
            print_orientation="landscape" if width_cm >= height_cm else "portrait",
        )
        self._doc.insert_style(pl)
        self._page_layout_name = name
        return name

    def _prepare_bg_image(self, path: str, width_cm: float, height_cm: float) -> str:
        """Downscale an oversized background bitmap before embedding.

        A bitmap master-page fill is one *style* (deduped), but Impress
        recomposites it fresh for every page that uses it, not once --
        verified empirically: a 10-page subset with a single 4096x2304
        source photo took 24.8s to export, 2.3s with that same master
        painted as a flat color (everything else identical). A multi-
        megapixel source photo turns a one-time decode into a per-slide
        cost multiplied by every slide sharing that master. Cap to 2x the
        slide's own pixel size -- already more than enough for a full-
        bleed background -- and skip entirely if already smaller.
        """
        return downscale_image(path, width_cm, height_cm)

    def _composite_tint_image(
        self, path: str, hex_color: str, alpha: float, width_cm: float, height_cm: float,
    ) -> tuple[str, bool]:
        """Bakes a uniform overlay tint directly into a downscaled copy of
        the background image -- replaces a per-slide alpha-composited
        overlay shape on top of one shared bitmap master with ONE
        flattened fill per (image, tint) combination, selected per slide
        via ``master_page`` -- a layout switched per slide (light/dark/
        etc.) instead of one image with a universal runtime overlay.
        Returns ``(path, baked)``: ``baked`` is False if compositing
        failed (corrupt/unreadable image), so the caller (``master_for``)
        can record the fallback and ``overlay_needed`` stays the single
        source of truth -- otherwise a page would get neither the baked
        tint nor the per-slide overlay shape.
        """
        downscaled = self._prepare_bg_image(path, width_cm, height_cm)
        try:
            from PIL import Image
            rgb = tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
            with Image.open(downscaled) as im:
                tint_layer = Image.new("RGB", im.size, rgb)
                composited = Image.blend(im.convert("RGB"), tint_layer, max(0.0, min(1.0, alpha)))
                fd, out_path = tempfile.mkstemp(suffix=".png")
                os.close(fd)
                composited.save(out_path)
                return out_path, True
        except Exception:
            return downscaled, False

    def _bake_footer_bar(
        self, img_path: str, footer: BoxGeometry, width_cm: float, height_cm: float,
    ) -> str | None:
        """Paints the footer bar directly onto a *copy* of the composited
        master image at its exact weasyprint-measured position, returning
        the new file's path -- never mutates ``img_path`` in place. On the
        ``_composite_tint_image`` failure path (or a source already
        smaller than the downscale target), ``img_path`` can be the
        theme's own original asset file on disk; writing into it would
        permanently corrupt the user's source image.
        ``style:repeat="stretch"`` maps the image linearly across the
        page regardless of its own aspect, so cm -> px uses the image's
        own size, not the original photo's.
        """
        try:
            from PIL import Image, ImageDraw
            rgb = tuple(int(footer.style.bg[i:i + 2], 16) for i in (1, 3, 5))
            alpha = max(0.0, min(1.0, footer.style.bg_alpha))
            with Image.open(img_path) as im:
                im = im.convert("RGB")
                sx, sy = im.width / width_cm, im.height / height_cm
                box = (footer.x * sx, footer.y * sy, (footer.x + footer.w) * sx, (footer.y + footer.h) * sy)
                if alpha >= 0.999:
                    ImageDraw.Draw(im).rectangle(box, fill=rgb)
                else:
                    overlay = Image.new("RGB", im.size, rgb)
                    mask = Image.new("L", im.size, 0)
                    ImageDraw.Draw(mask).rectangle(box, fill=round(alpha * 255))
                    im = Image.composite(overlay, im, mask)
                fd, out_path = tempfile.mkstemp(suffix=".png")
                os.close(fd)
                im.save(out_path)
            return out_path
        except Exception:
            return None

    def _pil_available(self) -> bool:
        if self._pil_ok is None:
            try:
                import PIL  # noqa: F401
                self._pil_ok = True
            except ImportError:
                self._pil_ok = False
        return self._pil_ok

    def _next_master_name(self, label: str) -> str:
        n = self._label_counters.get(label, 0) + 1
        self._label_counters[label] = n
        return label if n == 1 else f"{label} {n}"

    def overlay_needed(self, style: ResolvedStyle) -> bool:
        """Single source of truth for whether a separate per-slide overlay
        shape is still needed -- false whenever ``master_for`` already
        baked this exact (image, tint) into the master's own bitmap fill.
        Checked against the *recorded* outcome, not re-derived independently
        (a failed composite would otherwise disagree with itself: no
        overlay AND an untinted master)."""
        bg_image_ok = bool(style.bg_image_url) and os.path.isfile(style.bg_image_url)
        key = _bitmap_tint_key(style)
        if key is None:
            return bg_image_ok
        return key not in self._tint_baked_keys

    def footer_bar_baked(self, style: ResolvedStyle) -> bool:
        """Single source of truth for whether the footer bar is already
        painted into this style's master -- the per-slide footer frame
        must then render text only (no fill), or it double-paints."""
        key = _bitmap_tint_key(style)
        return key is not None and self._footer_baked.get(key, False)

    def master_for(
        self, style: ResolvedStyle, width_cm: float, height_cm: float,
        add_file: Callable[[str], str], footer: BoxGeometry | None = None,
    ) -> str:
        """Dedup'd master page for a slide's base background (solid/gradient/bitmap).

        A uniform overlay tint (every theme's light/dark section
        background -- ``is_uniform_tint``) is baked directly into the
        master's own bitmap fill: one master per (image, tint) pair,
        switched per slide via ``master_page`` -- "light" and "dark" are
        distinct master-page layouts, not one shared image recomposited
        with a universal per-slide overlay shape. Only a true multi-stop/
        angled gradient (``.layout-title``'s directional fade) still
        needs a separate per-slide overlay -- ``overlay_needed`` is the
        single source of truth for that. An opaque ``footer`` bar (the
        section's resolved footer box, if any) is baked in the same way.
        """
        pl_name = self.ensure_page_layout(width_cm, height_cm)
        bg_image_ok = bool(style.bg_image_url) and os.path.isfile(style.bg_image_url)
        tint_key = _bitmap_tint_key(style) if self._pil_available() else None
        tint_baked = tint_key is not None
        if tint_baked:
            key = tint_key
            self._tint_baked_keys.add(key)
        elif bg_image_ok:
            key = ("bitmap", style.bg_image_url)
        elif style.bg_gradient:
            key = ("gradient", tuple(style.bg_gradient), round(style.bg_angle_deg))
        else:
            key = ("solid", style.bg)
        cached = self._masters.get(key)
        if cached:
            return cached

        dp_name = f"SlidrBgDp{next(self._counter)}"
        dp = Style("drawing-page", name=dp_name)
        if key[0] in ("bitmap", "bitmap-tinted"):
            if tint_baked:
                img_path, _ = self._composite_tint_image(
                    style.bg_image_url, tint_key[2], tint_key[3], width_cm, height_cm,
                )
                footer_baked = False
                if footer is not None and footer.style.bg_alpha > 0:
                    baked_path = self._bake_footer_bar(img_path, footer, width_cm, height_cm)
                    if baked_path is not None:
                        img_path, footer_baked = baked_path, True
                self._footer_baked[key] = footer_baked
            else:
                img_path = self._prepare_bg_image(style.bg_image_url, width_cm, height_cm)
            uri = add_file(img_path)
            img_name = f"SlidrBgImg{next(self._counter)}"
            # draw:fill-image is family-less, same as draw:gradient/
            # draw:opacity -- append to styles.xml office:styles (same
            # container, same resolution scope as the gradient path,
            # confirmed working) rather than insert_style(automatic=True),
            # which would place it in content.xml where this master's
            # styles.xml drawing-page style couldn't resolve it.
            img = DrawFillImage(name=img_name, url=uri)
            self._doc.styles.get_element("office:styles").append(img)
            dp.set_properties(
                {"draw:fill": "bitmap", "draw:fill-image-name": img_name,
                 "style:repeat": "stretch"},
                area="drawing-page",
            )
        elif key[0] == "gradient":
            grad_name = self.gradient_name(style.bg_gradient, style.bg_angle_deg)
            dp.set_properties(
                {"draw:fill": "gradient", "draw:fill-gradient-name": grad_name},
                area="drawing-page",
            )
        else:
            dp.set_properties(
                {"draw:fill": "solid", "draw:fill-color": key[1] or "#ffffff"},
                area="drawing-page",
            )
        # Master backgrounds must live in styles.xml automatic-styles directly:
        # insert_style(automatic=True) targets content.xml, but a master-page's
        # draw_style_name only resolves drawing-page styles from styles.xml
        # automatic-styles (odfdo pitfall, verified against document.py/styles.py).
        self._doc.styles.get_element("office:automatic-styles").append(dp)

        label = _master_label(key, tint_key[2] if tint_baked else None)
        master_name = self._next_master_name(label)
        mp = StyleMasterPage(name=master_name, page_layout=pl_name, draw_style_name=dp_name)
        self._doc.insert_style(mp)
        self._masters[key] = master_name
        return master_name
