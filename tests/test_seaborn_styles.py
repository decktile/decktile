# SPDX-FileCopyrightText: 2026 Reza Jelveh
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for seaborn style loading -- CSS theme parsing and palette fallback."""

from decktile.render.seaborn import _css_theme_rcparams, set_theme


class TestCssThemeRcparams:
    """Verify CSS themes are parsed into correct matplotlib rcParams."""

    def test_kcd_vietnam_facecolor(self):
        style = _css_theme_rcparams("kcd_vietnam")
        assert style is not None
        assert style["axes.facecolor"] == "#F6ECD9"

    def test_kcd_vietnam_edgecolor(self):
        style = _css_theme_rcparams("kcd_vietnam")
        assert style["axes.edgecolor"] == "#7A0504"

    def test_kcd_vietnam_text_color(self):
        style = _css_theme_rcparams("kcd_vietnam")
        assert style["text.color"] == "#3a2020"

    def test_kcd_vietnam_patch_edge(self):
        style = _css_theme_rcparams("kcd_vietnam")
        assert style["patch.edgecolor"] == "#F1C560"

    def test_kcd_vietnam_tick_colors(self):
        style = _css_theme_rcparams("kcd_vietnam")
        assert style["xtick.color"] == "#7a6a5a"

    def test_kcd_vietnam_font(self):
        style = _css_theme_rcparams("kcd_vietnam")
        assert "Roboto" in style["font.sans-serif"]

    def test_kubecon_japan_facecolor(self):
        style = _css_theme_rcparams("kubecon_japan")
        assert style is not None
        assert style["axes.facecolor"] == "#f5f6fa"

    def test_kubecon_japan_edgecolor(self):
        style = _css_theme_rcparams("kubecon_japan")
        assert style["axes.edgecolor"] == "#3939D8"

    def test_kubecon_japan_text_color(self):
        style = _css_theme_rcparams("kubecon_japan")
        assert style["text.color"] == "#2a2a5a"

    def test_kubecon_japan_patch_edge(self):
        style = _css_theme_rcparams("kubecon_japan")
        assert style["patch.edgecolor"] == "#DB1E3D"

    def test_kubecon_japan_tick_colors(self):
        style = _css_theme_rcparams("kubecon_japan")
        assert style["xtick.color"] == "#6a7a99"

    def test_missing_theme_returns_none(self):
        assert _css_theme_rcparams("nonexistent") is None

    def test_default_theme_returns_style(self):
        style = _css_theme_rcparams("default")
        assert style is not None
        assert isinstance(style, dict)


class TestSetTheme:
    """Verify set_theme applies CSS styles and falls back to seaborn palettes."""

    def test_kcd_vietnam_applies_style(self):
        set_theme("kcd_vietnam")
        from decktile.render import seaborn

        assert seaborn._style is not None
        assert seaborn._palette is None

    def test_kubecon_japan_applies_style(self):
        set_theme("kubecon_japan")
        from decktile.render import seaborn

        assert seaborn._style is not None
        assert seaborn._palette is None

    def test_default_theme_applies_style(self):
        set_theme("default")
        from decktile.render import seaborn

        assert seaborn._style is not None
        assert seaborn._palette is None

    def test_muted_is_palette_fallback(self):
        set_theme("muted")
        from decktile.render import seaborn

        assert seaborn._palette == "muted"
        assert seaborn._style is None

    def test_deep_is_palette_fallback(self):
        set_theme("deep")
        from decktile.render import seaborn

        assert seaborn._palette == "deep"

    def test_unknown_falls_back_to_palette(self):
        set_theme("nonexistent_style_xyz")
        from decktile.render import seaborn

        assert seaborn._palette == "nonexistent_style_xyz"

    def test_empty_string_defaults_to_paired(self):
        set_theme("")
        from decktile.render import seaborn

        assert seaborn._palette == "Paired"

    def test_backward_compat_alias(self):
        from decktile.render.seaborn import set_palette, set_theme

        assert set_palette is set_theme


class TestStyleModulePalette:
    """A style module's seaborn_palette must reach the chart colors."""

    BAR = 'plt.bar(["a"], [1])'

    def test_ossummit_europe_bars_use_brand_coral(self):
        from decktile.render.seaborn import render_seaborn_svg

        set_theme("ossummit_europe")
        svg = render_seaborn_svg(self.BAR)
        assert svg is not None
        assert "#e05845" in svg.lower()

    def test_palette_survives_applying_theme_twice(self):
        from decktile.render.seaborn import render_seaborn_svg

        set_theme("ossummit_europe")
        set_theme("ossummit_europe")
        svg = render_seaborn_svg(self.BAR)
        assert "#e05845" in svg.lower()


class TestPredictygraphThemes:
    def test_hami_from_predictygraph(self):
        import pytest

        pytest.importorskip("seaborn")
        import decktile.render.seaborn as sb

        sb.set_theme("hami")
        assert sb._palette[0] == "#16a34a"
        assert sb._style["text.color"] == "#1e293b"

    def test_kubecon_na_chart_theme(self):
        import pytest

        pytest.importorskip("seaborn")
        import decktile.render.seaborn as sb

        sb.set_theme("kubecon_na")
        assert sb._palette[:2] == ["#113E82", "#D62293"]
        assert sb._style["patch.edgecolor"] == "#ffffff"

    def test_toml_file_extends_with_seaborn_section(self, tmp_path):
        import pytest

        pytest.importorskip("seaborn")
        import decktile.render.seaborn as sb

        f = tmp_path / "brand.toml"
        f.write_text('schema = 1\nextends = "hami"\n[seaborn]\npalette = ["blue", "#112233"]\n"grid.color" = "muted"\n')
        sb.set_theme(str(f))
        assert sb._palette == ["#2563eb", "#112233"]
        assert sb._style["grid.color"] == "#64748b"

    def test_missing_toml_theme_file(self, tmp_path):
        import pytest

        with pytest.raises(FileNotFoundError):
            set_theme(str(tmp_path / "nope.toml"))
