"""ODF Style registries built from resolved (weasyprint-derived) styles.

Every registry dedups by a hashable key derived from ResolvedStyle so two
elements with identical computed style share one odfdo Style object. Each
``*_style``/``*_name`` method inserts into the document immediately (no
deferred batch-insert pass) -- odfdo dedups by name internally and this
keeps the registration/use sites next to each other.
"""

from __future__ import annotations

import math
import os

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


@dataclass(frozen=True)
class _TextKey:
    fg: str
    font_family: str
    font_size_px: float
    weight: str
    italic: bool
    text_align: str


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

    def __init__(self, document: Document) -> None:
        self._doc = document
        self._fonts: set[str] = set()
        self._paragraph: dict[_TextKey, str] = {}
        self._run: dict[_TextKey, str] = {}
        self._graphic: dict[_GraphicKey, str] = {}
        self._table_cells: dict[tuple, str] = {}
        self._overlay: dict[tuple, tuple[str, str | None]] = {}
        self._gradients: dict[tuple, str] = {}
        self._opacities: dict[tuple, str] = {}
        self._masters: dict[tuple, str] = {}
        self._page_layout_name: str | None = None
        self._page_w: float = 0.0
        self._page_h: float = 0.0
        self._counter = count(1)

    # ---- fonts ----

    def ensure_font(self, family: str) -> None:
        if not family or family in self._fonts:
            return
        self._fonts.add(family)
        face = Style(
            "font-face", font_name=family, font_family=family,
            font_family_generic="swiss", font_pitch="variable",
        )
        self._doc.insert_style(face)
        self._doc.insert_style(face.clone, default=True)

    # ---- text (paragraph default + inline run) styles ----

    def paragraph_style(self, style: ResolvedStyle) -> str:
        """Automatic (content.xml) style -- verified empirically: Impress's
        draw:text-box only resolves text:p/text:span against automatic
        styles, silently ignoring an identical common (styles.xml) style
        (same family of pitfall as the table-cell/master-background ones)."""
        key = _TextKey(style.fg, style.font_family, style.font_size_px,
                      style.font_weight, style.font_italic, style.text_align)
        cached = self._paragraph.get(key)
        if cached:
            return cached
        self.ensure_font(style.font_family)
        name = f"SlidrP{next(self._counter)}"
        s = Style("paragraph", name=name)
        s.set_properties(area="paragraph", align=style.text_align)
        s.set_properties(
            area="text", color=style.fg, font=style.font_family,
            font_family=style.font_family, family_generic="swiss",
            size=px_to_pt(style.font_size_px), weight=style.font_weight,
            font_style="italic" if style.font_italic else "normal",
        )
        self._doc.insert_style(s, automatic=True)
        self._paragraph[key] = name
        return name

    def run_style(self, fg: str, font_family: str, font_size_px: float,
                 bold: bool, italic: bool) -> str:
        key = _TextKey(fg, font_family, font_size_px,
                      "bold" if bold else "normal", italic, "")
        cached = self._run.get(key)
        if cached:
            return cached
        self.ensure_font(font_family)
        name = f"SlidrT{next(self._counter)}"
        s = Style("text", name=name, bold=bold, italic=italic)
        s.set_properties(
            area="text", color=fg, font=font_family, font_family=font_family,
            family_generic="swiss", size=px_to_pt(font_size_px),
        )
        self._doc.insert_style(s, automatic=True)
        self._run[key] = name
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
            "draw:auto-grow-height": "true",
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
        el = Element.from_tag(
            f'<draw:gradient draw:name="{name}" draw:style="linear" '
            f'draw:angle="{odf_deg:.0f}deg" draw:start-color="{start_hex}" '
            f'draw:end-color="{end_hex}" draw:start-intensity="100%" '
            f'draw:end-intensity="100%" draw:border="0%"/>'
        )
        self._doc.styles.get_element("office:styles").append(el)
        self._gradients[key] = name
        return name

    def opacity_name(self, stops: list[tuple[float, str, float]], angle_deg: float) -> str | None:
        """Per-axis transparency gradient name, or None if fully opaque throughout.

        ODF ``draw:opacity`` values are *transparency* (0%=opaque, 100%=fully
        transparent) -- inverted from CSS alpha. A flat run of equal alphas
        (common: kubecon_japan's gradient is 0.85 throughout) is approximated
        with ``draw:border`` holding the start value before the real fade.
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
            f'draw:start="{(1 - start_alpha) * 100:.0f}%" '
            f'draw:end="{(1 - end_alpha) * 100:.0f}%" '
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

    def master_for(
        self, style: ResolvedStyle, width_cm: float, height_cm: float,
        add_file: Callable[[str], str],
    ) -> str:
        """Dedup'd master page for a slide's base background (solid/gradient/bitmap).

        A gradient-over-image overlay (if any) is a separate per-slide shape
        (``overlay_style``) -- ODF master backgrounds support exactly one fill.
        """
        pl_name = self.ensure_page_layout(width_cm, height_cm)
        bg_image_ok = bool(style.bg_image_url) and os.path.isfile(style.bg_image_url)
        if bg_image_ok:
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
        if key[0] == "bitmap":
            uri = add_file(style.bg_image_url)
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

        master_name = f"SlidrMaster{next(self._counter)}"
        mp = StyleMasterPage(name=master_name, page_layout=pl_name, draw_style_name=dp_name)
        self._doc.insert_style(mp)
        self._masters[key] = master_name
        return master_name
