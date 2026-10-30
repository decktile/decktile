import pytest
from decktile.parser.markdown import parse
from decktile.parser.ast import Heading, Paragraph, Table, Quote, Card, Grid


def test_parse_simple():
    doc = parse("---\ntheme: test\n---\n\n# Title\n\ntext")
    assert len(doc.slides) == 1
    assert doc.meta.theme == "test"


def test_heading():
    doc = parse("---\ntheme: t\n---\n\n# Title\n\ntext")
    slide = doc.slides[0]
    assert any(isinstance(n, Heading) and n.level == 1 for n in slide.children)


def test_table():
    doc = parse("---\ntheme: t\n---\n\n| a | b |\n|---|---|\n| 1 | 2 |")
    slide = doc.slides[0]
    assert any(isinstance(n, Table) for n in slide.children)


def test_quote():
    doc = parse("---\ntheme: t\n---\n\n> quoted text")
    slide = doc.slides[0]
    assert any(isinstance(n, Quote) for n in slide.children)


def test_slides():
    doc = parse("---\ntheme: t\n---\n\n## slide 1\n\n---\n\n## slide 2")
    assert len(doc.slides) == 2


def test_parse_slide_notes_keep_line_breaks():
    doc = parse("---\ntheme: t\n---\n\n<!--\n- first point\n  - nested\n- second point\n-->\n\n## Slide")
    assert doc.slides[0].notes == "- first point\n  - nested\n- second point"


def test_parse_slide_notes_keep_paragraph_gaps_within_one_comment():
    doc = parse("---\ntheme: t\n---\n\n<!--\nfirst paragraph\n\nsecond paragraph\n-->\n\n## Slide")
    assert doc.slides[0].notes == "first paragraph\n\nsecond paragraph"


def test_parse_slide_notes_separate_comments_joined_with_blank_line():
    doc = parse("---\ntheme: t\n---\n\n<!-- first comment -->\n\n## Slide\n\n<!-- second comment -->")
    assert doc.slides[0].notes == "first comment\n\nsecond comment"


def test_parse_slide_notes_first_line_indentation_preserved():
    doc = parse("---\ntheme: t\n---\n\n<!--\n  - indented from the start\n-->\n\n## Slide")
    assert doc.slides[0].notes == "  - indented from the start"


def test_hidden_slide():
    doc = parse("---\ntheme: t\n---\n\n# First\n\n---\n\n@hidden\n\n# Hidden\n\n---\n\n# Third")
    assert len(doc.slides) == 2
    from decktile.parser.ast import Heading
    headings = []
    for s in doc.slides:
        for n in s.children:
            if isinstance(n, Heading):
                headings.append(n.content[0].content)
    assert headings == ["First", "Third"]


def test_hide_alias():
    doc = parse("---\ntheme: t\n---\n\n# First\n\n---\n\n@hide\n\n# Hidden\n\n---\n\n# Third")
    assert len(doc.slides) == 2


def test_metric_parses_as_card():
    doc = parse("---\ntheme: t\n---\n\n::: card {metric}\n10x\nOperational cost improvement\n:::")
    slide = doc.slides[0]
    cards = [n for n in slide.children if isinstance(n, Card)]
    assert len(cards) == 1
    assert cards[0].header == "10x"
    assert cards[0].body == ["Operational cost improvement"]
    assert "metric" in (cards[0].class_ or "")


def test_card_label_attribute_parses_as_free_text_not_class():
    doc = parse('---\ntheme: t\n---\n\n::: card {focus, label="Q2"}\n### Q2\nbody\n:::')
    slide = doc.slides[0]
    cards = [n for n in slide.children if isinstance(n, Card)]
    assert cards[0].label == "Q2"
    assert "focus" in (cards[0].class_ or "")
    assert "label" not in (cards[0].class_ or "")


def test_metric_auto_groups_into_grid():
    doc = parse("---\ntheme: t\n---\n\n::: card {metric}\n10x\nSpeed\n:::\n\n::: card {metric}\n50%\nUtilization\n:::")
    slide = doc.slides[0]
    grids = [n for n in slide.children if isinstance(n, Grid)]
    assert len(grids) == 1
    assert grids[0].cols == 2
    assert all("metric" in (c.class_ or "") for c in grids[0].children)


def test_metrics_layout_detected():
    doc = parse("---\ntheme: t\n---\n\n## Key Metrics\n\n::: card {metric}\n10x\nSpeed\n:::\n\n::: card {metric}\n50%\nUtilization\n:::\n\n::: card {metric}\n10x\nDensity\n:::")
    slide = doc.slides[0]
    assert slide.layout == "metrics-3"


def test_metrics_with_explicit_grid():
    doc = parse("---\ntheme: t\n---\n\n::: grid {cols=2}\n::: card {metric}\n10x\nSpeed\n:::\n\n::: card {metric}\n50%\nUtil\n:::\n:::")
    slide = doc.slides[0]
    assert slide.layout == "metrics-2"


def test_metrics_two_cards():
    doc = parse("---\ntheme: t\n---\n\n::: card {metric}\nA\nB\n:::\n\n::: card {metric}\nC\nD\n:::")
    slide = doc.slides[0]
    assert slide.layout == "metrics-2"


def test_metric_single_line():
    doc = parse("---\ntheme: t\n---\n\n::: card {metric}\n99%\n:::")
    slide = doc.slides[0]
    card = [n for n in slide.children if isinstance(n, Card)][0]
    assert card.header == "99%"
    assert card.body == []


def test_autoplay_parsed():
    doc = parse("---\nautoplay: 7\n---\n\n# Title\n\ntext")
    assert doc.meta.autoplay == 7


def test_autoplay_default_seven():
    doc = parse("---\ntheme: t\n---\n\n# Title\n\ntext")
    assert doc.meta.autoplay == 7


def _cards(md: str) -> list:
    nodes = parse("---\ntitle: t\n---\n\n" + md).slides[0].children
    return [c for n in nodes for c in (n.children if isinstance(n, Grid) else [n]) if isinstance(c, Card)]


def test_parse_card_text_after_code_block_kept():
    card = _cards("::: card\n### C\n```python\nx = 1\n```\nAfter the code.\n:::\n")[0]
    assert card.body == ["After the code."]
    assert card.children[0].content == "x = 1"


def test_parse_card_text_after_nested_fence_kept():
    md = "::: card\n### Outer\n::: card\n### Inner\n:::\nAfter the inner card.\n:::\n"
    outer = _cards(md)[0]
    assert outer.body == ["After the inner card."]


def test_parse_paragraph_touching_card_kept_separate():
    """No blank line between a card and a paragraph: the fence marker used to
    merge into the paragraph, dropping text after the card."""
    nodes = parse("---\ntitle: t\n---\n\nBefore.\n::: card\n### A\n:::\nAfter.\n").slides[0].children
    texts = [n.content[0].content for n in nodes if isinstance(n, Paragraph)]
    assert texts == ["Before.", "After."]
    assert sum(isinstance(n, Card) for n in nodes) == 1


def test_parse_notes_strips_blockquote_marker():
    from decktile.parser.ast import Notes
    nodes = parse("---\ntitle: t\n---\n\n::: notes\n> quoted note\n:::\n").slides[0].children
    notes = next(n for n in nodes if isinstance(n, Notes))
    assert notes.content == "quoted note"


def test_group_cards_without_blank_lines_before_paragraph():
    """Cards written back to back, then a paragraph: one grid, then the
    paragraph -- not the first card alone, the paragraph, then the rest."""
    md = "".join(f"::: card {{tag={t}}}\n### {t}\nx\n:::\n" for t in ("cyan", "green", "red"))
    nodes = parse("---\ntitle: t\n---\n\n" + md + "\nAfter.\n").slides[0].children
    assert [type(n).__name__ for n in nodes] == ["Grid", "Paragraph"]
    assert [c.tag for c in nodes[0].children] == ["cyan", "green", "red"]


def test_directive_inside_code_fence_is_left_as_code():
    from decktile.parser.ast import AttrNode
    from decktile.parser.markdown import parse
    md = "## S\n\n```markdown\n@video clip.mp4\n@layout two-col\n```\n"
    slide = parse(md).slides[0]
    assert not any(isinstance(n, AttrNode) for n in slide.children)
    code = [n for n in slide.children if getattr(n, "language", None) == "markdown"]
    assert code and "@video clip.mp4" in code[0].content
