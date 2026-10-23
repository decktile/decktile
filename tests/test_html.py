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


def test_default_theme_h1_bold_and_h3_matches_converged_theme_size():
    """h1 font-weight and h3 font-size were the only two sizes where
    default.css lagged all 5 real conference themes (h1 missing bold,
    h3 still at the old 1.3em instead of the converged 1.15em)."""
    css = default_theme()
    assert "h1 { font-size: 2.5em; font-weight: 700; }" in css
    assert "h3 { font-size: 1.15em; }" in css


def test_base_css_has_h3_underline_and_kicker_eyebrow_treatment():
    """h3::after and the kicker's uppercase/letter-spaced treatment were
    duplicated identically across every real theme but missing from the
    shared base -- promoted as structural defaults (colors untouched,
    still resolved via the existing --color-accent-primary/var(--font-
    mono) variables)."""
    css = base_css()
    assert "h3::after {" in css
    assert "border-bottom: 2px solid var(--color-accent-primary);" in css
    assert "text-transform: uppercase" in css
    assert "letter-spacing: 0.05em" in css


def test_base_css_table_sizing_is_compact_not_oversized():
    """Default table font-size (0.85em) and cell padding (0.5em 0.65em)
    rendered rows visibly oversized relative to the rest of the slide
    body -- tightened to match the compactness of card/list text."""
    css = base_css()
    assert "table { border-collapse: collapse; width: 100%; margin: 0.5em 0; font-size: 0.75em; }" in css
    assert "th, td { padding: 0.4em 0.6em;" in css


def test_default_theme_font_family_matches_converged_theme_choice():
    """default.css was the only one of 6 themes still on "Segoe UI" --
    all 5 real conference themes independently converged on Roboto."""
    assert 'font-family: Roboto, Arial, "Helvetica Neue", sans-serif;' in default_theme()


def test_default_theme_watermark_sits_left_of_page_number():
    """Watermark anchored to --section-padding-h (same var .slide-num
    uses) plus a gap, so it clears the page-number column generically
    instead of overlapping it at the old 4%/5% base.css position.
    bottom: 0.48em (not 1em) vertically centers the watermark against
    .slide-num's own 0.6em-font-size text box, not just bottom-aligning
    the two boxes."""
    css = default_theme()
    assert "right: calc(var(--section-padding-h) + var(--watermark-gap));" in css
    assert "bottom: 0.48em;" in css


def test_video_sync_wired_in_both_presenter_and_main_branches():
    """Presenter and main windows are separate documents (window.open),
    each with its own independent <video> for the same slide -- playing
    one never touched the other without this wiring over the existing
    BroadcastChannel."""
    html = _full_page(
        "---\ntitle: T\n---\n\n## Video Slide\n\n@video assets/demo/clip.mp4\n"
    )
    assert "_wireVideoSync('#pres-main', bc);" in html
    assert "_wireVideoSync('body > section', bc);" in html
    assert "e.data.video" in html


def test_base_css_has_timeline_layouts():
    """@layout timeline-vertical / timeline-horizontal and ::: card
    {focus} need no parser changes (generic @layout <name> -> .layout-
    <name>, generic bare-word card attr -> .card.<word>) -- only CSS.
    Assert both spines specifically (not just the grid container rule):
    the vertical spine was accidentally dropped in an edit that this
    test, checking only "grid" presence, didn't catch."""
    css = base_css()
    assert ".layout-timeline-vertical .grid::before" in css
    assert ".layout-timeline-horizontal .grid::before" in css
    assert ".card.focus" in css
