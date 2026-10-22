"""weasyprint layout box-tree adapter: resolves per-Elem geometry + style for ODP.

Isolated here because it reads weasyprint's private layout API
(``HTML(...).render().pages[i]._page_box``, box internals). weasyprint is
pinned (``pyproject.toml``); ``tests/test_geometry.py`` guards the
attributes this module relies on so an upgrade breaking them fails loudly
here, not as a silently-wrong ODP render.

HTML/PDF rendering never import this module; it is the ODP-only consumer
of ``Elem.box``.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from slidr.render.ir import BoxGeometry, Elem, ResolvedStyle, SlideIR

PX_TO_CM = 2.54 / 96.0


GLOBAL_TAGS = {"code"}  # inline constructs with no per-instance id: resolve once, globally


def annotate_geometry(
    ir_slides: list[SlideIR],
    doc: Any,
    assembled_css: str,
    dims: tuple[int, int],
    source_dir: Path | None = None,
) -> tuple[dict[str, BoxGeometry], dict[str, ResolvedStyle]]:
    """Render ir_slides via weasyprint and fill every Elem.box in place.

    Returns ``({slide.id: BoxGeometry}, {tag: ResolvedStyle})``: the first
    for each slide's root ``<section>`` (slide/master background); the
    second for inline constructs with no per-instance id (currently just
    ``code``, for its themed mono font) -- resolved once from the first
    occurrence found anywhere, since the CSS rule that styles it (e.g.
    ``code { font-family: var(--font-mono) }``) never varies per instance.
    """
    from weasyprint import HTML

    from slidr.render.html import render_from_ir

    html_str = render_from_ir(ir_slides, doc, assembled_css, dims)
    base_url = f"{source_dir}/" if source_dir else "."
    rendered = HTML(string=html_str, base_url=base_url).render()

    by_id: dict[str, Elem] = {}
    for slide in ir_slides:
        _index(slide.elements, by_id)

    section_box: dict[str, BoxGeometry] = {}
    global_tags: dict[str, ResolvedStyle] = {}
    seen: set[str] = set()
    white = (1.0, 1.0, 1.0)
    for page in rendered.pages:
        _walk(page._page_box, by_id, section_box, seen, None, white, global_tags)
    return section_box, global_tags


def _index(elems: list[Elem], by_id: dict[str, Elem]) -> None:
    for e in elems:
        by_id[e.id] = e
        if e.children:
            _index(e.children, by_id)


def _sid_of(box: Any) -> str | None:
    el = getattr(box, "element", None)
    if el is None:
        return None
    try:
        return el.get("data-slidr-id")
    except Exception:
        return None


def _walk(
    box: Any,
    by_id: dict[str, Elem],
    section_box: dict[str, BoxGeometry],
    seen: set[str],
    section_origin: tuple[float, float] | None,
    parent_bg: tuple[float, float, float],
    global_tags: dict[str, ResolvedStyle],
) -> None:
    tag = getattr(box, "element_tag", None) or ""
    sid = _sid_of(box)
    has_rect = hasattr(box, "border_box_x")
    bg_rgb = parent_bg

    if tag in GLOBAL_TAGS and tag not in global_tags:
        global_tags[tag] = _resolve_style(box, parent_bg)

    if has_rect and (sid not in seen if sid else True):
        style = _resolve_style(box, parent_bg)
        bg_rgb = style.bg_rgb01  # already composited with parent_bg in _resolve_style

        if tag == "section" and sid:
            section_origin = (box.border_box_x(), box.border_box_y())
            section_box[sid] = BoxGeometry(
                x=0.0, y=0.0,
                w=box.border_width() * PX_TO_CM, h=box.border_height() * PX_TO_CM,
                style=style,
            )
            seen.add(sid)
        elif sid and sid in by_id:
            ox, oy = section_origin or (box.border_box_x(), box.border_box_y())
            elem = by_id[sid]
            substyles = (
                _collect_substyles(box, bg_rgb) if elem.kind in ("card", "table", "list")
                else {}
            )
            elem.box = BoxGeometry(
                x=(box.border_box_x() - ox) * PX_TO_CM,
                y=(box.border_box_y() - oy) * PX_TO_CM,
                w=box.border_width() * PX_TO_CM,
                h=box.border_height() * PX_TO_CM,
                style=style,
                substyles=substyles,
            )
            seen.add(sid)

    for child in getattr(box, "children", None) or []:
        _walk(child, by_id, section_box, seen, section_origin, bg_rgb, global_tags)


_SUBTAGS = {"h3", "p", "th", "td", "tr", "li"}


def _collect_substyles(
    box: Any, bg_rgb: tuple[float, float, float],
) -> dict[str, ResolvedStyle]:
    """First-seen style per descendant tag inside one Elem's subtree.

    ``tr`` needs both parity classes (CSS zebra striping is
    ``tr:nth-child(even)``), so the first two ``tr`` occurrences are kept
    as ``tr:odd``/``tr:even`` instead of one first-match. ``li::marker``
    is a real pseudo-element box (``element_tag`` suffixed accordingly),
    not derived from ``li``.
    """
    out: dict[str, ResolvedStyle] = {}
    tr_seen = 0

    def walk(b: Any, parent_bg: tuple[float, float, float], in_tbody: bool) -> None:
        nonlocal tr_seen
        tag = getattr(b, "element_tag", None) or ""
        bg_rgb_here = parent_bg
        next_in_tbody = in_tbody or tag == "tbody"
        if hasattr(b, "border_box_x") or tag.endswith("::marker"):
            style = _resolve_style(b, parent_bg)
            bg_rgb_here = style.bg_rgb01
            base_tag = tag.split("::")[0]
            if base_tag == "tr" and in_tbody:
                # nth-child scopes to the row's parent (tbody) -- a <thead>
                # row is never a zebra-stripe candidate at all.
                key = "tr:odd" if tr_seen == 0 else "tr:even"
                if tr_seen < 2:
                    out.setdefault(key, style)
                tr_seen += 1
            elif base_tag != "tr" and (tag in _SUBTAGS or tag.endswith("::marker")):
                out.setdefault(tag, style)
        for c in getattr(b, "children", None) or []:
            walk(c, bg_rgb_here, next_in_tbody)

    for child in getattr(box, "children", None) or []:
        walk(child, bg_rgb, False)
    return out


def _resolve_style(box: Any, parent_bg: tuple[float, float, float]) -> ResolvedStyle:
    s = box.style

    fg_rgb = _rgb01(s["color"])
    bg_color = s["background_color"]
    bg_rgb01 = _rgb01(bg_color)
    bg_alpha = float(bg_color.alpha or 0.0)
    bg_gradient, bg_angle, bg_image_url, bg_image_rgb01, bg_image_alpha = (
        _resolve_background_image(s["background_image"])
    )

    if bg_gradient or bg_image_url:
        # A box with its own background-image isn't "transparent" in the
        # visual sense even when background-color alpha is 0 -- its own
        # image/gradient already determines what descendants see through.
        # Composite onto white (the assumed photo brightness), never onto
        # an unrelated ancestor's flat color (e.g. the <body> screen-mode
        # letterboxing color, which never renders behind a slide section).
        composited = _composite((1.0, 1.0, 1.0), bg_image_rgb01, bg_image_alpha)
    else:
        composited = _composite(parent_bg, bg_rgb01, bg_alpha)

    radius_dims = s["border_top_left_radius"]
    border_radius = _dim_px(radius_dims[0]) if isinstance(radius_dims, tuple) else 0.0

    weight = s["font_weight"]
    font_weight = "bold" if (isinstance(weight, int) and weight >= 600) else "normal"
    font_italic = s["font_style"] in ("italic", "oblique")

    font_family_tuple = s["font_family"]
    font_family = font_family_tuple[0] if font_family_tuple else ""

    style = ResolvedStyle(
        bg=_hex(composited),
        bg_alpha=bg_alpha,
        fg=_hex(fg_rgb),
        border_color=_hex(_rgb01(s["border_left_color"], fg_rgb)),
        border_width=float(s["border_left_width"]) if s["border_left_width"] else 0.0,
        border_radius=border_radius,
        font_family=font_family,
        font_size_px=float(s["font_size"]),
        font_weight=font_weight,
        font_italic=font_italic,
        text_align=s["text_align_all"] or "left",
        bg_gradient=bg_gradient,
        bg_angle_deg=bg_angle,
        bg_image_url=bg_image_url,
        bg_rgb01=composited,
        padding_top=_dim_px(s["padding_top"]),
        padding_right=_dim_px(s["padding_right"]),
        padding_bottom=_dim_px(s["padding_bottom"]),
        padding_left=_dim_px(s["padding_left"]),
    )
    return style


def _resolve_background_image(
    layers: tuple,
) -> tuple[
    list[tuple[float, str, float]] | None, float, str,
    tuple[float, float, float], float,
]:
    """Returns (gradient stops, angle, image url, representative rgb01, alpha).

    The representative color/alpha is the stop-average, used only to
    approximate "what this box's own background visually reads as" for
    compositing child text/fills -- never for the ODF fill itself (that
    uses the full gradient/bitmap via styles.py).
    """
    gradient = None
    angle = 180.0
    url = ""
    rep_rgb01 = (1.0, 1.0, 1.0)
    rep_alpha = 1.0
    for kind, val in layers or ():
        if kind == "linear-gradient":
            angle = math.degrees(val.direction) if val.direction_type == "angle" else angle
            stops = []
            rgb01_stops = []
            alphas = []
            n = len(val.colors)
            for idx, (color, pos) in enumerate(zip(val.colors, val.stop_positions)):
                if pos is not None and getattr(pos, "unit", "") == "%":
                    offset = pos.value / 100.0
                else:
                    # no stop position declared (e.g. every theme's
                    # `linear-gradient(var(--bg-overlay), var(--bg-overlay))`)
                    # -- evenly space rather than collapsing every stop to 0.
                    offset = idx / (n - 1) if n > 1 else 0.0
                alpha = 1.0 if color.alpha is None else float(color.alpha)
                rgb01 = _rgb01(color)
                stops.append((offset, _hex(rgb01), alpha))
                rgb01_stops.append(rgb01)
                alphas.append(alpha)
            gradient = stops
            rep_rgb01 = tuple(sum(c[i] for c in rgb01_stops) / len(rgb01_stops) for i in range(3))
            rep_alpha = sum(alphas) / len(alphas)
        elif kind == "url" and val.startswith("file://"):
            url = val[len("file://"):]
    return gradient, angle, url, rep_rgb01, rep_alpha


def _rgb01(color: Any, currentcolor: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> tuple[float, float, float]:
    if color == "currentcolor":
        return currentcolor
    r, g, b = color.coordinates
    return (_clamp01(r), _clamp01(g), _clamp01(b))


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def _composite(
    parent_rgb01: tuple[float, float, float],
    child_rgb01: tuple[float, float, float],
    alpha: float,
) -> tuple[float, float, float]:
    if alpha <= 0.0:
        return parent_rgb01
    if alpha >= 1.0:
        return child_rgb01
    return tuple(c * alpha + p * (1 - alpha) for c, p in zip(child_rgb01, parent_rgb01))  # type: ignore[return-value]


def _hex(rgb01: tuple[float, float, float]) -> str:
    return "#%02x%02x%02x" % tuple(round(c * 255) for c in rgb01)


def _dim_px(dim: Any) -> float:
    return float(dim.value) if getattr(dim, "unit", "px") == "px" else 0.0
