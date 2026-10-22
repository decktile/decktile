"""Observable ODF contract for the ODP renderer: real render() -> real odfdo
Document round-trip, asserting what a consumer (LibreOffice, a reviewer
opening the file) would see -- not internal call patterns."""

import re
import zipfile
from pathlib import Path

from odfdo import Document as OdfDocument

from slidr.parser.markdown import parse
from slidr.render.html import base_css, default_theme
from slidr.render.odp import render


def _build(md: str, tmp_path: Path, theme_css: str = "", source_dir: Path | None = None) -> OdfDocument:
    doc = parse(md)
    css = theme_css or default_theme()
    out = tmp_path / "out.odp"
    render(doc, out, base_css(), css, source_dir=source_dir or tmp_path)
    return OdfDocument(str(out))


def _frames(odp: OdfDocument, page_index: int = 0):
    page = odp.body.get_draw_pages()[page_index]
    return page.get_frames()


def test_page_size_matches_content_dimensions(tmp_path):
    odp = _build("---\ntitle: T\nsize: 1280x720\n---\n\n# Hello\n", tmp_path)
    pl = odp.get_style("page-layout", "SlidrPageLayout")
    props = pl.get_properties()
    w_cm = float(props["fo:page-width"].rstrip("cm"))
    h_cm = float(props["fo:page-height"].rstrip("cm"))
    assert abs(w_cm - 1280 * 2.54 / 96) < 0.01
    assert abs(h_cm - 720 * 2.54 / 96) < 0.01


def test_light_section_background_is_white(tmp_path):
    odp = _build("---\ntitle: T\n---\n\n# Hello\n", tmp_path)
    page = odp.body.get_draw_pages()[0]
    master = odp.styles.get_master_page(0) if page.master_page == "" else \
        next(m for m in odp.styles.master_pages if m.name == page.master_page)
    dp = odp.get_style("drawing-page", master.draw_style_name)
    props = dp.get_properties()
    assert props.get("draw:fill-color", "").lower() == "#ffffff"


def test_dark_variant_section_uses_dark_colors(tmp_path):
    theme = (
        default_theme()
        + "\nsection[data-theme=\"dark\"] { --color-background: #1a1a2e; "
        "--color-foreground: #e0e0e0; }\n"
    )
    odp = _build(
        "---\ntitle: T\n---\n\n@variant dark\n\n# Dark Slide\n", tmp_path, theme_css=theme,
    )
    page = odp.body.get_draw_pages()[0]
    master = next(m for m in odp.styles.master_pages if m.name == page.master_page)
    dp = odp.get_style("drawing-page", master.draw_style_name)
    assert dp.get_properties().get("draw:fill-color", "").lower() == "#1a1a2e"


def test_card_frame_has_fill_and_border(tmp_path):
    md = (
        "---\ntitle: T\n---\n\n## Cards\n\n"
        "::: card {tag=green}\n### Head\nBody text\n:::\n"
    )
    odp = _build(md, tmp_path)
    frames = _frames(odp)
    card_frame = next(f for f in frames if "Body text" in f.get_formatted_text())
    style = odp.get_style("graphic", card_frame.style)
    props = style.get_properties(area="graphic")
    assert props.get("draw:fill") == "solid"
    assert props.get("draw:fill-color")
    assert props.get("draw:stroke") == "solid"


def test_list_items_are_real_odf_list_items(tmp_path):
    md = "---\ntitle: T\n---\n\n## List\n\n- one\n- two\n- three\n"
    odp = _build(md, tmp_path)
    frames = _frames(odp)
    list_frame = next(f for f in frames if "one" in f.get_formatted_text())
    box = list_frame.get_text_box()
    items = box.get_elements("text:list/text:list-item")
    assert len(items) == 3
    assert [i.text_content.strip() for i in items] == ["one", "two", "three"]


def test_list_bullet_has_colored_level_style(tmp_path):
    """Bullet color must be an inline style:text-properties child on the
    level style -- Impress ignores @text:style-name for bullet color."""
    md = "---\ntitle: T\n---\n\n## List\n\n- one\n- two\n"
    odp = _build(md, tmp_path)
    frames = _frames(odp)
    list_frame = next(f for f in frames if "one" in f.get_formatted_text())
    box = list_frame.get_text_box()
    odf_list = box.get_element("text:list")
    list_style_name = odf_list.get_attribute("text:style-name")
    assert list_style_name
    list_style = odp.get_style("list", list_style_name)
    bullet = list_style.get_element("text:list-level-style-bullet")
    assert bullet.get_attribute("text:bullet-char") == "\u25b8"
    text_props = bullet.get_element("style:text-properties")
    assert text_props is not None
    assert text_props.get_attribute("fo:color")


def test_table_header_and_body_cells_have_distinct_styles(tmp_path):
    md = (
        "---\ntitle: T\n---\n\n## Table\n\n"
        "| A | B |\n|---|---|\n| r1 | x |\n| r2 | y |\n"
    )
    odp = _build(md, tmp_path)
    frames = _frames(odp)
    table_frame = next(f for f in frames if f.get_element("table:table") is not None)
    table = table_frame.get_element("table:table")
    header_cell = table.get_element("table:table-row/table:table-cell")
    body_cell = table.get_elements("table:table-row")[1].get_element("table:table-cell")
    assert header_cell.get_attribute("table:style-name") != body_cell.get_attribute("table:style-name")


def test_frames_stay_within_page_bounds(tmp_path):
    md = (
        "---\ntitle: T\nsize: 1280x720\n---\n\n## Content\n\n"
        "Some body text.\n\n- item one\n- item two\n"
    )
    odp = _build(md, tmp_path)
    pl = odp.get_style("page-layout", "SlidrPageLayout")
    props = pl.get_properties()
    page_w = float(props["fo:page-width"].rstrip("cm"))
    page_h = float(props["fo:page-height"].rstrip("cm"))
    for frame in _frames(odp):
        x = float((frame.pos_x or "0cm").rstrip("cm"))
        y = float((frame.pos_y or "0cm").rstrip("cm"))
        w = float((frame.width or "0cm").rstrip("cm"))
        h = float((frame.height or "0cm").rstrip("cm"))
        assert x >= -0.01 and y >= -0.01
        assert x + w <= page_w + 0.5  # small tolerance for auto-grow text frames
        assert y + h <= page_h + 0.5


def test_speaker_notes_present(tmp_path):
    md = "---\ntitle: T\n---\n\n<!--\nremember to smile\n-->\n\n# Hello\n"
    odp = _build(md, tmp_path)
    page = odp.body.get_draw_pages()[0]
    notes = page.get_element("presentation:notes")
    assert notes is not None
    assert "remember to smile" in notes.text_content


def test_missing_background_image_degrades_to_solid_fill(tmp_path):
    """A theme referencing a nonexistent background image must not crash --
    degrade to the resolved solid/gradient fill (regression: this exact
    scenario crashed in kubecon_japan.css before the fix)."""
    theme = default_theme() + '\nsection { background-image: url("does/not/exist.png"); }\n'
    odp = _build("---\ntitle: T\n---\n\n# Hello\n", tmp_path, theme_css=theme)
    assert odp.body.get_draw_pages()  # just must not have raised


def test_background_image_embeds_as_bitmap_master_fill(tmp_path):
    """A real (existing) background-image file must become a native ODF
    bitmap master fill -- this path had zero coverage before (every example
    theme's --bg-image path was broken), confirmed empirically via soffice
    render; pin it so it can't silently regress back to the solid fallback."""
    from PIL import Image

    img_path = tmp_path / "bg.png"
    Image.new("RGB", (4, 4), (10, 20, 30)).save(img_path)
    theme = default_theme() + f'\nsection {{ background-image: url("bg.png"); }}\n'
    odp = _build("---\ntitle: T\n---\n\n# Hello\n", tmp_path, theme_css=theme)

    page = odp.body.get_draw_pages()[0]
    master = next(m for m in odp.styles.master_pages if m.name == page.master_page)
    dp = odp.get_style("drawing-page", master.draw_style_name)
    assert dp.get_properties().get("draw:fill") == "bitmap"
    img_name = dp.get_properties().get("draw:fill-image-name")
    assert img_name
    # fill-image is family-less; confirm its definition landed in styles.xml
    # office:styles (not content.xml, where this master's style couldn't
    # resolve it -- regression this test guards against).
    styles_xml = odp.styles.get_element("office:styles").serialize()
    assert f'draw:name="{img_name}"' in styles_xml


def test_multi_stop_gradient_keeps_middle_color(tmp_path):
    """draw:gradient's base 2-stop model would drop a middle CSS stop's hue
    -- loext:gradient-stop children must carry every stop."""
    theme = (
        default_theme()
        + "\nsection[data-theme=\"dark\"] { background-image: "
        "linear-gradient(135deg, #1a0000 0%, #7a0504 60%, #280202 100%); }\n"
    )
    odp = _build(
        "---\ntitle: T\n---\n\n@variant dark\n\n# Hello\n", tmp_path, theme_css=theme,
    )
    styles_xml = odp.styles.get_element("office:styles").serialize()
    assert 'loext:color-value="#7a0504"' in styles_xml


def test_svg_logo_keeps_its_own_aspect_ratio(tmp_path):
    """PIL can't open SVG at all (raises on Image.open) -- the fallback
    was a hardcoded 3.0x1.3cm (2.31 aspect) box regardless of the real
    logo, which visibly compresses any wide logo (regression: a real
    1305x298 (4.38 aspect) SVG logo rendered squeezed into 2.31).
    Unit-tested directly against _logo_frame: the full pipeline now
    resolves a themed logo via the section::before pseudo-element box
    instead (its own, separate, already-correct aspect handling) --
    _logo_frame is the fallback for a theme with no --logo CSS wiring,
    not exercised by a normal build."""
    from slidr.render.odp import _logo_frame

    logo = tmp_path / "logo.svg"
    logo.write_text('<svg viewBox="0 0 1305 298" xmlns="http://www.w3.org/2000/svg"></svg>')
    frame = _logo_frame(str(logo), lambda p: p, page_w=33.87, page_h=19.05)
    aspect = float(frame.width.rstrip("cm")) / float(frame.height.rstrip("cm"))
    assert abs(aspect - 1305 / 298) < 0.05


def test_dark_slide_uses_logo_dark(tmp_path):
    logo = tmp_path / "logo.png"
    logo_dark = tmp_path / "logo-dark.png"
    from PIL import Image

    Image.new("RGB", (100, 50), "black").save(logo)
    Image.new("RGB", (100, 50), "white").save(logo_dark)
    md = (
        "---\ntitle: T\nlogo: logo.png\nlogo_dark: logo-dark.png\n---\n\n"
        "@variant dark\n\n# Dark\n\n---\n\n# Light\n"
    )
    odp = _build(md, tmp_path)
    pages = odp.body.get_draw_pages()
    dark_logo_uri = next(f.get_image().url for f in pages[0].get_frames() if f.get_image())
    light_logo_uri = next(f.get_image().url for f in pages[1].get_frames() if f.get_image())
    assert dark_logo_uri != light_logo_uri


def test_theme_no_logo_decision_not_overridden_by_fallback(tmp_path):
    """The Python-side fallback (doc.meta.logo/logo_dark directly) is for
    a theme with no section::before CSS at all -- NOT for a box that
    exists but legitimately resolves to no image (background-image:
    none). Regression: a logo reappearing on a slide the theme
    explicitly hides it on, bypassing the CSS cascade's own decision."""
    from PIL import Image

    logo = tmp_path / "logo.png"
    Image.new("RGB", (100, 50), "black").save(logo)
    md = "---\ntitle: T\nlogo: logo.png\n---\n\n@layout title\n\n# Hello\n"
    theme = default_theme() + (
        "\nsection::before { content: ''; position: absolute; width: 10%; "
        "height: 10%; background: var(--logo); }\n"
        "\n.layout-title::before { background-image: none; }\n"
    )
    odp = _build(md, tmp_path, theme_css=theme)
    frames = _frames(odp)
    assert not any(f.get_image() for f in frames)


def test_speaker_links_render_as_text(tmp_path):
    """Speaker contact links (github/linkedin/etc) are built from
    elem.attrs in html.py's own rendering but were never read by the ODP
    path at all -- elem.text only carries name+role, so the ODP speaker
    frame silently dropped all contact info."""
    md = (
        "---\ntitle: T\n---\n\n# Hello\n\n"
        "@speaker name=\"Jane Doe\" role=\"Engineer\" "
        "github=\"jdoe\" linkedin=\"https://linkedin.com/in/jdoe\"\n"
    )
    odp = _build(md, tmp_path)
    frames = _frames(odp)
    speaker_frame = next(f for f in frames if "Jane Doe" in f.get_formatted_text())
    text = speaker_frame.get_formatted_text()
    assert "jdoe" in text
    assert "linkedin.com/in/jdoe" in text


def test_shapes_have_explicit_incrementing_z_index(tmp_path):
    """A bitmap-filled master page changes how LibreOffice resolves
    z-order for shapes with no explicit draw:z-index: an un-indexed
    overlay rect was confirmed (empirically, via corner-color sampling)
    to paint ABOVE a z-index=0 text frame in that specific case, dimming
    all text/content to near-black -- identical shapes with no master
    page stack correctly in document order. Every shape must carry an
    explicit, unique z-index so paint order never depends on that
    default."""
    from PIL import Image

    img_path = tmp_path / "bg.png"
    Image.new("RGB", (4, 4), (80, 80, 150)).save(img_path)
    theme = default_theme() + '\nsection { background-image: url("bg.png"); }\n'
    md = "---\ntitle: T\n---\n\n@variant dark\n\n# Hello\n\nBody text.\n"
    odp = _build(md, tmp_path, theme_css=theme)

    page = odp.body.get_draw_pages()[0]
    shapes = [c for c in page.children if c.tag in ("draw:rect", "draw:frame")]
    assert len(shapes) >= 2  # at least the overlay + one content frame
    z_indices = [s.get_attribute("draw:z-index") for s in shapes]
    assert all(z is not None for z in z_indices)
    assert [int(z) for z in z_indices] == list(range(len(shapes)))


def test_uniform_tint_bakes_into_master_no_overlay_shape(tmp_path):
    """A uniform tint (every gradient stop the same color+alpha) over a
    background image must be baked into the master's own bitmap fill --
    not rendered as a separate per-slide overlay shape recomposited on
    every page sharing that master (a layout switched per slide, not one
    shared image plus a universal runtime overlay)."""
    from PIL import Image

    img_path = tmp_path / "bg.png"
    Image.new("RGB", (8, 8), (80, 80, 150)).save(img_path)
    theme = default_theme() + (
        '\nsection { background: linear-gradient(rgba(255,255,255,0.9), '
        'rgba(255,255,255,0.9)), url("bg.png") left top / cover no-repeat; }\n'
    )
    md = "---\ntitle: T\n---\n\n# Hello\n"
    odp = _build(md, tmp_path, theme_css=theme)
    page = odp.body.get_draw_pages()[0]
    rects = [c for c in page.children if c.tag == "draw:rect"]
    assert rects == []


def test_distinct_tints_over_same_image_get_distinct_masters(tmp_path):
    """Light and dark variants over the same source image select
    different master pages -- a layout switch per slide, not one shared
    master."""
    from PIL import Image

    img_path = tmp_path / "bg.png"
    Image.new("RGB", (8, 8), (80, 80, 150)).save(img_path)
    theme = default_theme() + (
        '\nsection { background: linear-gradient(rgba(255,255,255,0.9), '
        'rgba(255,255,255,0.9)), url("bg.png") left top / cover no-repeat; }\n'
        '\nsection[data-theme="dark"] { background: linear-gradient(rgba(0,0,0,0.8), '
        'rgba(0,0,0,0.8)), url("bg.png") left top / cover no-repeat; }\n'
    )
    md = "---\ntitle: T\n---\n\n# Light\n\n---\n\n@variant dark\n\n# Dark\n"
    odp = _build(md, tmp_path, theme_css=theme)
    pages = odp.body.get_draw_pages()
    masters = {p.get_attribute("draw:master-page-name") for p in pages}
    assert len(masters) == 2


def test_code_block_gets_per_token_colored_spans(tmp_path):
    """Code blocks must be pygments-highlighted (matching the HTML
    renderer), not one flat mono Paragraph -- a keyword/string/comment
    token must get a different run-style color than plain text."""
    md = '---\ntitle: T\n---\n\n## Code\n\n```yaml\nkey: "value"\n```\n'
    odp = _build(md, tmp_path)
    frames = _frames(odp)
    code_frame = next(f for f in frames if "key" in f.get_formatted_text())
    spans = code_frame.get_elements("descendant::text:span")
    assert len(spans) > 1
    colors = set()
    for s in spans:
        style_name = s.get_attribute("text:style-name")
        style = odp.get_style("text", style_name)
        props = style.get_properties(area="text")
        colors.add(props.get("fo:color"))
    assert len(colors) > 1


def test_table_columns_and_rows_get_explicit_dims(tmp_path):
    """Without explicit column-width/row-height, Impress falls back to a
    fixed per-column/-row default wider/taller than the HTML table."""
    md = "---\ntitle: T\n---\n\n## Table\n\n| A | B |\n|---|---|\n| x | y |\n"
    odp = _build(md, tmp_path)
    frames = _frames(odp)
    table_frame = next(f for f in frames if f.get_element("table:table") is not None)
    table = table_frame.get_element("table:table")
    col = table.get_element("table:table-column")
    col_style = odp.get_style("table-column", col.get_attribute("table:style-name"))
    assert col_style.get_properties(area="table-column").get("style:column-width")
    row = table.get_element("table:table-row")
    row_style = odp.get_style("table-row", row.get_attribute("table:style-name"))
    assert row_style.get_properties(area="table-row").get("style:row-height")


def test_table_body_cell_has_own_run_style(tmp_path):
    """Body cell text must carry an explicit font-size run style -- without
    one, Impress falls back to its own (larger) default text size. Select
    the body-cell span specifically: the header cell always had a run
    style, so a non-specific lookup would pass even before the fix."""
    md = "---\ntitle: T\n---\n\n## Table\n\n| A |\n|---|\n| body text |\n"
    odp = _build(md, tmp_path)
    frames = _frames(odp)
    table_frame = next(f for f in frames if "body text" in f.get_formatted_text())
    spans = table_frame.get_elements("descendant::text:span")
    body_span = next(s for s in spans if s.text == "body text")
    style = odp.get_style("text", body_span.get_attribute("text:style-name"))
    assert style.get_properties(area="text").get("fo:font-size")


def test_arrow_icon_renders_as_svg_image_frame(tmp_path):
    """A ::: arrow block with a {icon:...} directive must embed the icon
    as an image frame -- it was previously stripped to an empty frame."""
    md = (
        "---\ntitle: T\n---\n\n## Compare\n\n"
        "::: card\nLeft\n:::\n\n::: arrow\n\n{icon:arrow-right size=48}\n:::\n\n"
        "::: card\nRight\n:::\n"
    )
    odp = _build(md, tmp_path)
    frames = _frames(odp)
    images = [f.get_element("draw:image") for f in frames]
    images = [img for img in images if img is not None]
    assert any((img.get_attribute("xlink:href") or "").endswith(".svg") for img in images)


def test_footer_and_slide_num_render_as_shapes(tmp_path):
    """<footer>/.slide-num are template-injected (shell.html), not AST
    nodes -- they carried no data-slidr-id and were silently dropped by
    the by-id geometry match, so they never appeared in ODP at all.
    default.css sets no --footer-bg (CSS default: transparent) -- the
    frame must have no fill, not an opaque box painted over the gradient
    (a composited-background regression: ResolvedStyle.bg is the parent
    chain's opaque color even at bg_alpha=0)."""
    md = "---\ntitle: T\nfooter: My Conference 2026\npaginate: true\n---\n\n# Hello\n"
    odp = _build(md, tmp_path)
    frames = _frames(odp)
    footer_frame = next(f for f in frames if "My Conference 2026" in f.get_formatted_text())
    assert any(f.get_formatted_text().strip() == "1" for f in frames)
    gfx = odp.get_style("graphic", footer_frame.get_attribute("draw:style-name"))
    assert gfx.get_properties(area="graphic").get("draw:fill") == "none"


def test_footer_bar_gets_its_own_box_not_its_text_line_box(tmp_path):
    """weasyprint recurses into a <footer>'s own LineBox/TextBox children,
    which carry the same element_tag -- capturing without first-match-wins
    landed on the text's own tight, unstyled line-box geometry (zero
    padding, transparent, text-width only) instead of the footer block's
    real resolved box, silently losing a themed full-width footer bar
    entirely (reported as a transparent, narrow frame on every slide)."""
    md = "---\ntitle: T\nfooter: Conference 2026\n---\n\n# Hello\n"
    theme = default_theme() + (
        '\nfooter { left: 0; right: 0; bottom: 0; background: #123456; '
        'padding: 1em 2em; }\n'
    )
    odp = _build(md, tmp_path, theme_css=theme)
    frames = _frames(odp)
    footer_frame = next(f for f in frames if "Conference 2026" in f.get_formatted_text())
    gfx = odp.get_style("graphic", footer_frame.get_attribute("draw:style-name"))
    props = gfx.get_properties(area="graphic")
    assert props.get("draw:fill") == "solid"
    assert props.get("draw:fill-color") == "#123456"
    pl = odp.get_style("page-layout", "SlidrPageLayout")
    page_w_cm = float(pl.get_properties()["fo:page-width"].rstrip("cm"))
    frame_w_cm = float(footer_frame.get_attribute("svg:width").rstrip("cm"))
    assert frame_w_cm > page_w_cm * 0.9


def test_icon_svg_has_no_mismatched_intrinsic_dims(tmp_path):
    """render_icon's no-explicit-size path emits width="24" height="1em"
    (meant for inline HTML flow) -- LibreOffice's SVG import reads these
    as the icon's real aspect ratio instead of the viewBox, rendering a
    visibly squashed icon. The embedded file must carry no width/height/
    style attributes on the <svg> tag, leaving viewBox as the only
    aspect-ratio signal."""
    md = "---\ntitle: T\n---\n\n::: card\n### {icon:zap} Label\n:::\n"
    odp = _build(md, tmp_path)
    z = zipfile.ZipFile(tmp_path / "out.odp")
    svgs = [n for n in z.namelist() if n.startswith("Pictures/") and n.endswith(".svg")]
    assert svgs
    svg = z.read(svgs[0]).decode()
    tag = svg[: svg.index(">")]
    assert not re.search(r'(?<![-\w])width="', tag)
    assert not re.search(r'(?<![-\w])height="', tag)
    assert 'viewBox="' in tag
