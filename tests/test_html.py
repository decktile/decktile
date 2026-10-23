"""Tests for the HTML renderer's element rendering."""
from slidr.parser.markdown import parse
from slidr.render.html import _render_elem, base_css, default_theme, render
from slidr.render.ir import Elem


def test_speaker_linkedin_uses_brand_svg_not_placeholder():
    """linkedin= renders the inlined brand mark, never a Lucide placeholder.

    Lucide dropped all brand icons upstream, so a mapped `linkedin` Lucide
    icon resolves to a "not found" placeholder box. The speaker renderer must
    use the inlined Simple Icons mark instead.
    """
    elem = Elem(kind="speaker", attrs={"name": "The Anh",
                                       "linkedin": "linkedin.com/in/ntheanh201"})
    html = _render_elem(elem)

    # LinkedIn line-icon path signature is present.
    assert "M16 8a6 6 0 0 1 6 6" in html
    # The Lucide "not found" placeholder must never leak through.
    assert "lucide-placeholder" not in html
    assert "data-missing-icon" not in html
    # Link targets the profile.
    assert 'href="https://linkedin.com/in/ntheanh201"' in html


def test_speaker_github_still_uses_lucide_icon():
    """Non-brand contact links keep using their Lucide proxy icon."""
    elem = Elem(kind="speaker", attrs={"name": "The Anh",
                                       "github": "github.com/ntheanh201"})
    html = _render_elem(elem)

    assert "lucide" in html  # git-fork proxy still rendered
    assert "lucide-placeholder" not in html
    assert 'href="https://github.com/ntheanh201"' in html


def _title_html(md: str) -> str:
    from slidr.parser.markdown import parse
    from slidr.render.html import _render_slide
    from slidr.render.ir import build_ir
    return _render_slide(build_ir(parse(md))[0])


def test_contributor_renders_labelled_and_distinct_from_speaker():
    html = _title_html(
        "@speaker name=Reza role=Architect\n"
        "@contributor name=Thanh role=\"LFX Mentee\" github=github.com/loiht2\n"
    )
    assert 'class="speaker"' in html  # plain speaker div exists
    assert "Reza" in html and "Architect" in html
    assert 'class="speaker contributor"' in html  # distinct contributor variant
    assert '<span class="contributor-label">Contributor</span>' in html
    assert "Thanh" in html and "LFX Mentee" in html and "github.com/loiht2" in html


def test_contributor_label_override():
    html = _title_html("@contributor name=Thanh label=\"Research by\"\n")
    assert '<span class="contributor-label">Research by</span>' in html


def _full_page(md: str) -> str:
    doc = parse(md)
    return render(doc, default_theme(), base_css() + default_theme(), (1280, 720))


def test_presenter_autoplay_speed_controls_render_with_frontmatter_value():
    html = _full_page("---\ntheme: t\nautoplay: 12\n---\n\n# Title\n\ntext")
    assert 'id="pres-speed-dec"' in html
    assert 'id="pres-speed-inc"' in html
    assert '<span id="pres-speed-val"' in html
    assert ">12s<" in html


def test_autoplay_speed_is_a_mutable_variable_not_a_hardcoded_constant():
    """The old AUTOPLAY_INTERVAL was a module-level constant baked in at
    build time -- no way to adjust the cycle speed without rebuilding.
    Regression guard: the inlined script must declare a mutable variable
    the presenter's +/- buttons can reassign at runtime."""
    html = _full_page("---\ntheme: t\nautoplay: 7\n---\n\n# Title\n\ntext")
    assert "var autoplaySpeed = 7;" in html
    assert "AUTOPLAY_INTERVAL" not in html

