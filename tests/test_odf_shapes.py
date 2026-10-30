"""Unit tests for render/odf/shapes.py helpers."""

from decktile.render.odf.shapes import _normalize_svg_viewbox, _svg_dims


def test_normalize_svg_negative_origin():
    svg = '<svg viewBox="-10 -5 100 50" width="100%"><rect/></svg>'
    result = _normalize_svg_viewbox(svg)
    assert 'viewBox="0 0 110 55"' in result
    assert "<g transform" not in result  # no translate wrapper


def test_normalize_svg_positive_origin_unchanged():
    svg = '<svg viewBox="0 0 100 50" width="100%"><rect/></svg>'
    assert _normalize_svg_viewbox(svg) == svg


def test_normalize_svg_no_viewbox_unchanged():
    svg = '<svg width="100" height="50"><rect/></svg>'
    assert _normalize_svg_viewbox(svg) == svg


def test_svg_dims_preserves_aspect_ratio_within_max_width():
    svg = '<svg viewBox="0 0 500 300">'
    w, h = _svg_dims(svg, max_w_cm=50.0)
    assert abs(w / h - 500 / 300) < 0.01


def test_svg_dims_capped_by_max_width():
    svg = '<svg viewBox="0 0 500 300">'
    w, h = _svg_dims(svg, max_w_cm=5.0)
    assert w <= 5.0
    assert abs(w / h - 500 / 300) < 0.01


def test_svg_dims_no_viewbox_falls_back_to_16_9():
    svg = '<svg width="100" height="200">'
    w, h = _svg_dims(svg, max_w_cm=20.0)
    assert w == 20.0
    assert abs(h - 20.0 * 9 / 16) < 0.01
