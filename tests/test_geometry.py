"""Guards the private weasyprint layout API render/odf/geometry.py depends on.

If a weasyprint upgrade removes/renames any of these, this test fails
loudly here instead of silently producing a wrong ODP render.
"""

import importlib.metadata

from weasyprint import HTML

from slidr.render.ir import BoxGeometry, ResolvedStyle, SlideIR, Elem
from slidr.render.odf.geometry import annotate_geometry

EXPECTED_WEASYPRINT = "69."  # pinned major.minor; pyproject.toml requires >=69.0


def test_weasyprint_pinned_major_version():
    version = importlib.metadata.version("weasyprint")
    assert version.startswith(EXPECTED_WEASYPRINT), (
        f"weasyprint upgraded to {version}; re-verify render/odf/geometry.py's "
        "private box API (_page_box, border_box_x/y, border_width/height, "
        ".style[...], .element, .element_tag) against the new version."
    )


def test_box_tree_exposes_required_private_api():
    rendered = HTML(
        string='<html><body><section style="width:100px;height:50px;'
        'background:red;color:#fff"><div data-slidr-id="x">hi</div>'
        "</section></body></html>",
        base_url=".",
    ).render()
    page = rendered.pages[0]
    assert hasattr(page, "_page_box")
    box = page._page_box

    found = []

    def walk(b):
        found.append(b)
        for c in getattr(b, "children", None) or []:
            walk(c)

    walk(box)
    div_box = next(b for b in found if getattr(b, "element_tag", None) == "div")
    assert hasattr(div_box, "border_box_x") and hasattr(div_box, "border_box_y")
    assert hasattr(div_box, "border_width") and hasattr(div_box, "border_height")
    assert div_box.element.get("data-slidr-id") == "x"
    style = div_box.style
    for key in ("background_color", "background_image", "color", "border_left_color",
                "border_left_width", "border_top_left_radius", "font_family",
                "font_size", "font_weight", "text_align_all"):
        style[key]  # raises KeyError if the property name changed


def test_annotate_geometry_fills_elem_box():
    ir_slides = [SlideIR(id="s0", layout="content", elements=[
        Elem(kind="heading", id="e1", level=1, content="Hello"),
        Elem(kind="text", id="e2", content="Body text."),
    ])]

    class _Meta:
        footer = ""
        paginate = False
        theme_variant = "light"
        autoplay = False
        title = "T"
        transition = ""

    class _Doc:
        meta = _Meta()

    css = "section { width: 960px; height: 540px; background: #112233; color: #eee; } code { font-family: monospace; }"
    section_box, global_tags = annotate_geometry(ir_slides, _Doc(), css, (960, 540))

    assert "s0" in section_box
    assert section_box["s0"].style.bg == "#112233"
    assert ir_slides[0].elements[0].box is not None
    assert ir_slides[0].elements[1].box is not None
    # both elements sit inside the section's own bounds
    sb = section_box["s0"]
    for e in ir_slides[0].elements:
        assert 0 <= e.box.x <= sb.w
        assert 0 <= e.box.y <= sb.h
    # no <code> in this deck -> global_tags stays empty, not a crash
    assert "code" not in global_tags


def _ir_from(content: str):
    from slidr.parser.markdown import parse

    class _Meta:
        footer = ""
        paginate = False
        theme_variant = "light"
        autoplay = False
        title = "T"
        transition = ""

    class _Doc:
        meta = _Meta()

    from slidr.render.ir import build_ir

    doc = parse(content)
    return build_ir(doc), _Doc()


def test_background_image_ignores_unrelated_ancestor_bg():
    """A box with its own background-image isn't transparent for child
    compositing even when background-color alpha is 0 -- it must not
    inherit an unrelated ancestor's flat color (e.g. a <body> background
    meant only for screen-mode letterboxing, never visible behind a
    section)."""
    from slidr.render.ir import Elem, SlideIR

    ir_slides = [SlideIR(id="s0", layout="content", elements=[
        Elem(kind="heading", id="e1", level=1, content="Hello"),
    ])]

    class _Meta:
        footer = ""
        paginate = False
        theme_variant = "light"
        autoplay = False
        title = "T"
        transition = ""

    class _Doc:
        meta = _Meta()

    css = (
        "body { background: #1d1d6b; }"
        "section { width: 960px; height: 540px; color: #222;"
        " background: linear-gradient(rgba(255,255,255,0.96),rgba(255,255,255,0.96)),"
        " url(data:image/png;base64,); }"
    )
    section_box, _ = annotate_geometry(ir_slides, _Doc(), css, (960, 540))
    sb = section_box["s0"]
    assert sb.style.bg != "#1d1d6b"  # not the <body> leak
    r, g, b = int(sb.style.bg[1:3], 16), int(sb.style.bg[3:5], 16), int(sb.style.bg[5:7], 16)
    assert r > 200 and g > 200 and b > 200  # reads as near-white


def test_table_zebra_stripe_scoped_to_tbody():
    """CSS nth-child scopes to the row's parent: a <thead> row is never a
    zebra-stripe candidate, and the first striped <tbody> row is the
    *second* tbody row (nth-child(even)), not the second <tr> overall."""
    ir_slides, fake_doc = _ir_from(
        "---\ntitle: T\n---\n\n"
        "| A | B |\n|---|---|\n| r1 | x |\n| r2 | y |\n| r3 | z |\n"
    )
    css = (
        "section { width: 960px; height: 540px; }"
        "tr:nth-child(even) { background: #e8e8f0; }"
    )
    annotate_geometry(ir_slides, fake_doc, css, (960, 540))
    table_elem = next(e for e in ir_slides[0].elements if e.kind == "table")
    sub = table_elem.box.substyles
    assert sub["tr:odd"].bg != "#e8e8f0"
    assert sub["tr:even"].bg == "#e8e8f0"
