

def test_assemble_css_frontmatter_images_override_theme(tmp_path):
    """Frontmatter watermark/background were injected into base.css's :root,
    before the theme, so a theme's own --watermark/--bg-image always won and
    `none` could not remove another event's branding."""
    import weasyprint
    from slidr.parser.markdown import parse
    from slidr.render.html import base_css, load_theme, render
    from slidr.render.ir import assemble_css

    def image_urls(front: str) -> dict:
        doc = parse(f"---\ntheme: kubecon_japan\n{front}---\n\n## S\n\nBody.\n")
        theme = load_theme("kubecon_japan")
        css = assemble_css(base_css(), theme, (1280, 720), watermark=doc.meta.watermark,
                           background=doc.meta.background)
        page = weasyprint.HTML(string=render(doc, theme, css, (1280, 720)), base_url=str(tmp_path)).render().pages[0]
        found = {}

        def walk(b):
            if getattr(b, "element_tag", "") in ("section", "section::after"):
                found[b.element_tag] = [v for t, v in b.style["background_image"] if t == "url"]
            for c in getattr(b, "children", []):
                walk(c)
        walk(page._page_box)
        return found

    default = image_urls("")
    assert default["section"] and default["section::after"]  # theme art + watermark
    assert image_urls("background: none\nwatermark: none\n") == {"section": [], "section::after": []}
    custom = image_urls("watermark: assets/mine.svg\n")
    assert custom["section::after"][0].endswith("assets/mine.svg")


def test_build_ir_dot_in_blueprint_card_uses_blueprint_palette():
    """A dot fence inside ::: card {blueprint} draws light-on-blue with a
    transparent canvas; outside a blueprint card it stays a light panel."""
    from slidr.parser.markdown import parse
    from slidr.render.html import base_css, load_theme
    from slidr.render.ir import build_ir

    dot = "```dot\ndigraph { a -> b }\n```"
    md = f"---\ntheme: kubecon_japan\n---\n\n## S\n\n::: card {{blueprint}}\n{dot}\n:::\n\n{dot}\n"
    elems = build_ir(parse(md), base_css(), load_theme("kubecon_japan"))[0].elements
    card = next(e for e in elems if e.kind == "card")
    inside = card.children[0].svg
    outside = next(e for e in elems if e.kind == "code").svg
    assert ".graph > polygon { fill: none" in inside and "fill: #eaf4ff" in inside
    assert ".graph > polygon { fill: none" not in outside and "fill: #333" in outside
