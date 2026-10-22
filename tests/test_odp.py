"""Observable ODF contract for the ODP renderer: real render() -> real odfdo
Document round-trip, asserting what a consumer (LibreOffice, a reviewer
opening the file) would see -- not internal call patterns."""

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
