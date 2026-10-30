"""Tests for ```pdg blocks rendered with predictygraph."""

from decktile.render.pdg import render_pdg_svg, theme_css


def test_pdg_renders_svg():
    svg = render_pdg_svg('a "Application" .green\nb "GPU"\na -> b')
    assert svg is not None
    assert svg.lstrip().startswith("<svg")
    assert "Application" in svg


def test_pdg_blueprint_palette():
    svg = render_pdg_svg('a "App" .cyan', blueprint=True,
                         tag_colors={"cyan": ("#e0f7fa", "#00bcd4")})
    assert "#67d8ff" in svg.lower()
    assert "#e0f7fa" not in svg.lower()


def test_pdg_applies_theme_font_and_tag_colors():
    svg = render_pdg_svg('a "App" .green\nb "DB"\na -> b',
                         font_family="Liberation Mono", font_size=12,
                         tag_colors={"green": ("#e8f5e9", "#0fd05d")})
    assert "Liberation Mono" in svg
    assert "#e8f5e9" in svg.lower()


def test_pdg_block_css_overrides_theme():
    content = 'css { node.green { fill: #123456; } }\na "App" .green'
    svg = render_pdg_svg(content, tag_colors={"green": ("#e8f5e9", "#0fd05d")})
    assert "#123456" in svg
    assert "#e8f5e9" not in svg.lower()


def test_pdg_returns_none_on_syntax_error():
    assert render_pdg_svg('a -> b "unterminated') is None


def test_theme_css_maps_default_tag_to_plain_nodes():
    css = theme_css(tag_colors={"default": ("#fafafa", "#ddd"), "red": ("#fee", "")})
    assert "node { fill: #fafafa; stroke: #ddd; }" in css
    assert "node.red { fill: #fee; }" in css


def test_animated_pdg_moves_in_html_and_stays_still_in_print():
    from decktile.parser.markdown import parse
    from decktile.render.html import _render_elem, base_css, load_theme
    from decktile.render.ir import build_ir

    md = "## S\n\n```pdg\na -> b flow=forward\n```\n\n```pdg\nc -> d\n```\n"
    elems = [e for e in build_ir(parse(md), base_css(), load_theme("default"))[0].elements
             if e.kind == "code"]
    moving, still = elems
    assert "<animate" in moving.svg_live and "<animate" not in moving.svg
    assert still.svg_live == ""  # no animation, no second copy
    html = _render_elem(moving)
    assert 'class="pdg-live"' in html and 'class="pdg-still"' in html
