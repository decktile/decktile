import pytest
from slidr.parser.markdown import parse
from slidr.parser.ast import Heading, Paragraph, Table, Quote, Card, Grid


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
    from slidr.parser.ast import Heading
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
