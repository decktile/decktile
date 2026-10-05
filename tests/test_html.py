"""Tests for the HTML renderer's element rendering."""

from slidr.render.html import _render_elem
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
    assert '<div class="speaker">Reza' in html
    assert '<div class="speaker contributor"><span class="contributor-label">Contributor</span>' in html
    assert "Thanh" in html and "LFX Mentee" in html and "github.com/loiht2" in html


def test_contributor_label_override():
    html = _title_html("@contributor name=Thanh label=\"Research by\"\n")
    assert '<span class="contributor-label">Research by</span>' in html

