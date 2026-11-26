# SPDX-FileCopyrightText: 2026 Reza Jelveh
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for the HTML renderer's element rendering."""

from decktile.parser.markdown import parse
from decktile.render.html import _render_elem, base_css, default_theme, render
from decktile.render.ir import Elem


def test_speaker_linkedin_uses_brand_svg_not_placeholder():
    """linkedin= renders the inlined brand mark, never a Lucide placeholder.

    Lucide dropped all brand icons upstream, so a mapped `linkedin` Lucide
    icon resolves to a "not found" placeholder box. The speaker renderer must
    use the inlined Simple Icons mark instead.
    """
    elem = Elem(kind="speaker", attrs={"name": "The Anh", "linkedin": "linkedin.com/in/ntheanh201"})
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
    elem = Elem(kind="speaker", attrs={"name": "The Anh", "github": "github.com/ntheanh201"})
    html = _render_elem(elem)

    assert "lucide" in html  # git-fork proxy still rendered
    assert "lucide-placeholder" not in html
    assert 'href="https://github.com/ntheanh201"' in html


def _title_html(md: str) -> str:
    from decktile.parser.markdown import parse
    from decktile.render.html import _render_slide
    from decktile.render.ir import build_ir

    return _render_slide(build_ir(parse(md), base_css(), default_theme())[0])


def test_contributor_renders_labelled_and_distinct_from_speaker():
    html = _title_html('@speaker name=Reza role=Architect\n@contributor name=Thanh role="LFX Mentee" github=github.com/loiht2\n')
    assert 'class="speaker"' in html  # plain speaker div exists
    assert "Reza" in html and "Architect" in html
    assert 'class="speaker contributor"' in html  # distinct contributor variant
    assert '<span class="contributor-label">Contributor</span>' in html
    assert "Thanh" in html and "LFX Mentee" in html and "github.com/loiht2" in html


def test_contributor_label_override():
    html = _title_html('@contributor name=Thanh label="Research by"\n')
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
    html = _full_page("---\ntitle: T\n---\n\n## Video Slide\n\n@video assets/demo/clip.mp4\n")
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


def test_base_css_timeline_uses_space_evenly_autolayout():
    """Milestones auto-space along a fixed-length spine: the vertical grid
    grows to fill the slide body (flex: 1, not height: 100% -- weasyprint
    resolved that too tall and spilled cards onto a new page) and
    space-evenly distributes the cards over it."""
    css = base_css()
    assert "justify-content: space-evenly;\n  flex: 1;" in css
    assert ".layout-timeline-vertical .slide-body {" in css


def test_card_label_renders_as_distinct_span():
    html = _title_html('::: card {label="Q1"}\n### Q1 2026\nbody\n:::')
    assert '<span class="timeline-label">Q1</span>' in html
    assert "<h3>Q1 2026</h3>" in html


def test_render_notes_with_quotes_do_not_leak_into_slide():
    """Speaker notes reach the presenter via JSON; an unescaped data-notes
    attribute let a '"' in the notes end the attribute and spill the rest
    onto the slide."""
    html = _full_page('---\ntitle: T\n---\n\n<!-- He said "hello" <b>x</b> -->\n\n## S\n\nBody.')
    assert "data-notes" not in html
    assert "<b>x</b>" not in html.split("<body>", 1)[1].split("<script", 1)[0]


def test_render_card_text_escaped_once():
    html = _full_page("---\ntitle: T\n---\n\n## M\n\n::: card {metric}\n>80%\nutilization\n:::\n")
    assert "<h3>&gt;80%</h3>" in html
    assert "&amp;gt;" not in html


def test_render_table_cells_keep_inline_markup():
    html = _full_page("---\ntitle: T\n---\n\n## T\n\n| a | b |\n|---|---|\n| **bold** | `x>1` |\n")
    assert "<td><strong>bold</strong></td>" in html
    assert "<td><code>x&gt;1</code></td>" in html


def test_render_subtitle_inline_markdown():
    html = _full_page("---\ntitle: T\n---\n\n## Title\n@subtitle Use `nvidia.com/gpu` here\n\nBody.")
    subtitle = html.split('<p class="subtitle"', 1)[1].split("</p>", 1)[0]
    assert "<code>nvidia.com/gpu</code>" in subtitle
    assert "`" not in subtitle


def test_bare_emails_and_urls_become_links():
    from decktile.parser.markdown import parse
    from decktile.render.html import _render_elem
    from decktile.render.ir import build_ir

    md = "## S\n\nMail reza@dynamia.ai or https://decktile.github.io\n\n- in a list reza@dynamia.ai\n"
    html = "".join(_render_elem(e) for e in build_ir(parse(md), base_css(), default_theme())[0].elements)
    assert '<a href="mailto:reza@dynamia.ai">reza@dynamia.ai</a>' in html
    assert '<a href="https://decktile.github.io">https://decktile.github.io</a>' in html
    assert html.count("mailto:") == 2


def test_markdown_link_keeps_its_text():
    from decktile.parser.markdown import parse
    from decktile.render.html import _render_elem
    from decktile.render.ir import build_ir

    html = "".join(
        _render_elem(e) for e in build_ir(parse("## S\n\nSee [the docs](https://x.io/d)\n"), base_css(), default_theme())[0].elements
    )
    assert '<a href="https://x.io/d">the docs</a>' in html


def test_email_in_speaker_role_is_a_link():
    from decktile.render.html import _link_emails

    assert _link_emails("Mail reza@dynamia.ai now") == 'Mail <a href="mailto:reza@dynamia.ai">reza@dynamia.ai</a> now'
    assert _link_emails("https://x.io/a@b") == "https://x.io/a@b"


def test_mailto_links_keep_text_colour():
    css = base_css()
    assert 'a[href^="mailto:"]' in css and "color: inherit" in css


def test_grid_fill_spreads_rows_over_the_slide():
    """{fill}: rows of a short grid spread down the slide instead of leaving a band."""
    from weasyprint import HTML

    md = "---\ntitle: t\n---\n\n## Fill\n\n::: grid {cols=2, %s}\n" + "".join(f"::: card\n### C{i}\nx\n:::\n" for i in range(4)) + ":::\n"

    def row2_y(flag):
        from decktile.render.ir import assemble_css

        css = assemble_css(base_css(), default_theme(), (1280, 720))
        doc = HTML(string=render(parse(md % flag), default_theme(), css, (1280, 720))).render()
        page = doc.pages[0]._page_box

        def walk(box):
            yield box
            for c in getattr(box, "children", []):
                yield from walk(c)

        ys = [b.position_y for b in walk(page) if getattr(b, "element_tag", "") == "h3" and "C2" in "".join(b.element.itertext())]
        return ys[0], page.height

    plain, h = row2_y("plain-grid")
    filled, _ = row2_y("fill")
    assert filled > plain + h * 0.1
    assert "grid fill" in _full_page(md % "fill")


def test_timeline_steps_columns_with_label_above_heading():
    """timeline-steps: equal columns side by side, {label} above the ### heading."""
    from weasyprint import HTML

    from decktile.render.ir import assemble_css

    md = "---\ntitle: t\n---\n\n@layout timeline-steps\n\n## Agenda\n\n::: grid {cols=4}\n"
    md += "".join(f'::: card {{label="Part"}}\n### 0{i}\nTopic {i}\n:::\n' for i in range(1, 5)) + ":::\n"
    css = assemble_css(base_css(), default_theme(), (1280, 720))
    page = HTML(string=render(parse(md), default_theme(), css, (1280, 720))).render().pages[0]._page_box

    def walk(box):
        yield box
        for c in getattr(box, "children", []):
            yield from walk(c)

    def cls(b):
        el = getattr(b, "element", None)
        return el.get("class", "") if el is not None else ""

    cards = [b for b in walk(page) if getattr(b, "element_tag", "") == "div" and cls(b).split()[:1] == ["card"]]
    cards = list({id(b.element): b for b in cards}.values())
    assert len(cards) == 4
    xs = [c.position_x for c in cards]
    ws = [c.width for c in cards]
    assert xs == sorted(xs) and len({round(x) for x in xs}) == 4
    assert max(ws) - min(ws) < 2
    ys = {round(c.position_y) for c in cards}
    assert len(ys) == 1  # nothing alternates
    label = next(b for b in walk(page) if "timeline-label" in cls(b))
    h3 = next(b for b in walk(page) if getattr(b, "element_tag", "") == "h3")
    assert label.position_y < h3.position_y


STACK_MD = """---
title: t
---

## Stack

::: stack {gap=1em, arrows, bill}
| A | B |
| --- | --- |
| 1 | 2 |

```pdg
graph layout=row gap=10
x "left" width=200
y "right" width=200
```

```pdg
graph layout=row gap=10
z "below" width=300
```
:::
"""


def test_stack_parses_any_blocks_with_arrows_between():
    """::: stack: a table and diagrams in order, an arrow in each gap, gap and classes kept."""
    html = _full_page(STACK_MD)
    body = html[html.index('class="stack') :]
    assert body.startswith('class="stack bill arrows" style="--stack-gap: 1em"')
    order = [body.index(k) for k in ("<table", "stack-arrow", "pdg-plot", "stack-arrow", "pdg-plot")[:3]]
    assert order == sorted(order)
    assert body.count('class="stack-arrow"') == 2 * body.count('class="stack bill arrows"')  # one per gap


def test_stack_diagrams_drop_the_pdg_margin():
    """A diagram in a stack starts at its SVG's edge (no 16px margin), so its boxes line up
    with the table above; outside a stack the margin stays."""
    import re

    def first_x(md):
        html = _full_page(md)
        svg = html[html.index('<div class="pdg-plot"') :]
        return float(re.search(r'<rect x="([\d.]+)"', svg)[1])

    assert first_x(STACK_MD) == 0
    assert first_x(STACK_MD.replace("::: stack {gap=1em, arrows, bill}\n", "").replace("\n:::\n", "\n")) == 16


def test_stack_arrow_fence_marks_one_gap():
    """`::: arrow` between two blocks of a stack puts an arrow only in that gap."""
    md = STACK_MD.replace("{gap=1em, arrows, bill}", "{gap=1em}").replace(
        "\n```pdg\ngraph layout=row gap=10\nx", "\n::: arrow\n:::\n\n```pdg\ngraph layout=row gap=10\nx", 1
    )
    html = _full_page(md)
    stacks = html.count('class="stack arrows"')
    assert stacks and html.count('class="stack-arrow"') == stacks  # one arrow per stack: table -> first diagram
    body = html[html.index('class="stack arrows"') :]
    assert body.index("<table") < body.index("stack-arrow") < body.index("pdg-plot")


def test_stack_arrow_takes_the_theme_colour_through_var_chains():
    """--stack-arrow-color (or the accent), with var() chains resolved: PDF ignores currentColor."""
    theme = default_theme() + "\n:root { --brand: #123456; --stack-arrow-color: var(--brand); }\n"
    html = render(parse(STACK_MD), theme, base_css() + theme, (1280, 720))
    arrow = html[html.index('class="stack-arrow"') :]
    assert 'fill="#123456"' in arrow[: arrow.index("</svg>")]
