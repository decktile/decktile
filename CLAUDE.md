# CLAUDE.md — Slidr (Python)

Slidr is a Python CLI that turns markdown into styled HTML + PDF + ODP. Uses markdown-it-py for parsing, weasyprint for both PDF and ODP layout, odfdo for ODP, Jinja2 for templates. CSS passthrough, no CSS parser needed for HTML/PDF. ODP geometry and color come from weasyprint's own resolved layout, not a separate parser.

## Build & test

```bash
pdm install                # install deps
pdm run slidr slides.md    # build HTML
pdm run slidr slides.md --odp     # + ODP
pdm run slidr slides.md --pdf     # + PDF
pdm run slidr --dist slides.md    # HTML + assets as zip
pdm run pytest             # run tests
```

## Architecture

```
src/slidr/
├── __init__.py
├── __main__.py           # python -m slidr entry
├── cli.py                # Typer CLI (single callback pattern)
├── parser/
│   ├── ast.py            # Node types (Heading, Paragraph, Grid, Card, Table, Quote, ListNode, AttrNode, Inline)
│   └── markdown.py       # Main parser: frontmatter → slide split → directives → fenced extraction → markdown-it → token walk
├── plugins/
│   ├── fenced.py         # ::: card / ::: grid extraction (pre-process, not markdown-it plugin). Cards support nested fences, code blocks, lists
│   ├── directives.py     # @kicker / @speaker / @subtitle → HTML comment markers → post-process to AttrNode
│   ├── cards.py          # Auto-group consecutive Card nodes into Grid
│   └── layouts.py        # KNOWN_LAYOUTS registry + legacy apply_layout (HTML path)
├── theme/
│   ├── parser.py         # tinycss2: parse base.css + theme CSS → PPTX style dict (colors, fonts, padding)
│   └── loader.py         # Raw CSS passthrough + variable extraction (legacy)
├── render/
│   ├── ir.py             # AST → SlideIR intermediate representation. build_ir(), _convert_node(), _apply_layout_ir(). Elem.id (data-slidr-id) + Elem.box (BoxGeometry, filled by odf/geometry.py) for ODP only
│   ├── html.py           # Jinja2: SlideIR → HTML, with data-slidr-id on every emitted tag. render_from_ir() split out so odp.py renders the exact same IR/HTML pairing
│   ├── pdf.py            # weasyprint: HTML file → PDF
│   ├── odf/              # ODP renderer internals (see below)
│   ├── odp.py            # thin orchestrator: build_ir → odf.geometry.annotate_geometry → one DrawPage per slide via odf.shapes + odf.styles
│   └── templates/
│       ├── shell.html    # Main HTML template (Jinja2)
│       ├── presenter.html # Presenter view (grid: main slide | next preview / notes)
│       ├── base.css      # Structural CSS (reset, layout, screen/print media, nav bar)
│       ├── slidr.js      # Shared JS: navigation, fullscreen, presenter, wheel, keyboard
│       └── presenter.html # Presenter view template
└── themes/
    ├── default.css       # Built-in light theme (CSS variables, card, quote, table, tag colors)
    ├── kcd_vietnam.css   # KCD Vietnam theme
    └── kubecon_japan.css # KubeCon Japan theme
├── seaborn_styles/      # optional STYLE modules (CSS theme parsing is the default)
```

## ODP rendering (render/odf/)

ODP output is **geometry-driven**, not a second layout/paint engine: the
same HTML string (with a `data-slidr-id` on every element) is rendered
through weasyprint, and its resolved layout box tree supplies exact
position, size, and computed CSS style for each `Elem`.

```
render/odf/
├── geometry.py   # weasyprint box-tree adapter (private API, version-guarded
│                 # by tests/test_geometry.py). annotate_geometry()
│                 # fills Elem.box (BoxGeometry: x/y/w/h in cm, section-relative,
│                 # plus a ResolvedStyle) and Elem.box.substyles (first-seen
│                 # style per descendant tag: card h3/p, table th/td/tr:odd/
│                 # tr:even, list li/li::marker) by walking each Elem's own
│                 # subtree. A box's own background-image (gradient/photo)
│                 # is never backfilled from an unrelated ancestor's flat
│                 # color (e.g. <body>'s screen-mode letterboxing bg).
├── styles.py     # StyleRegistry: dedups odfdo Style objects from ResolvedStyle.
│                 # draw:gradient/draw:opacity are family-less in odfdo (built
│                 # as raw XML). Paragraph/run text styles MUST be inserted
│                 # automatic=True (content.xml): Impress silently ignores
│                 # an identical common/styles.xml text style. Table-cell fill
│                 # MUST go through style:graphic-properties (draw:fill-color),
│                 # not style:table-cell-properties (fo:background-color):
│                 # Impress tables are draw tables, not spreadsheet tables.
├── shapes.py     # Elem.kind -> Frame + real ODF semantics: text:list/
│                 # text:list-item (not manual bullets), table:table appended
│                 # directly to the Frame (not wrapped in draw:text-box), per
│                 # run text:span for inline bold/italic/code. CSS border-left
│                 # accents (quote/notes) render as a LineShape, not a full
│                 # draw:stroke outline. Card/table/notes text is parser
│                 # pre-expanded HTML (icons, bold): stripped + entity
│                 # decoded before use as literal ODF text.
└── __init__.py
```

### Known ODP limitations

- Lucide icons (inline SVG) have no ODF text equivalent and are dropped
  wherever they appear (headings, cards, tables, arrows) rather than
  rendered or faked.
- Logo placement uses a fixed top-right heuristic (`_logo_frame` in
  `odp.py`, same corner/size math as the old renderer), not the actual
  `section::before` pseudo-element box weasyprint computes for the HTML
  logo overlay -- position/size can drift from the HTML render for
  non-default logo aspect ratios.
- LibreOffice's text engine can wrap a borderline-width paragraph one
  line taller than weasyprint measured it, which can overlap a tightly
  stacked sibling frame below it (fixed-position frames don't reflow).
  `draw:auto-grow-height` keeps the text itself from clipping; it does
  not push siblings down.

## Parser pipeline

```
slides.md
  → split_frontmatter (YAML between --- markers)
  → split_slides (\n---\n)
  → per slide: parse_slide
      1. extract_notes (<!-- comment at start)
      2. preprocess_directives (@kicker → <!--attr:kicker:text-->)
      3. extract_fenced (::: card / ::: grid → Card/Grid nodes, content replaced with ◊FENCE_N markers)
      4. markdown_it.parse (gfm-like preset: tables, strikethrough, task lists)
      5. _tokens_to_nodes (heading_open→Heading, paragraph_open→Paragraph, blockquote_open→Quote, table_open→Table, etc.)
      6. interleave_fences (replace ◊FENCE_N markers with actual nodes)
      7. extract_attrs (<!--attr:type:value--> → AttrNode)
      8. group_cards (consecutive Card → Grid auto-wrap)
      9. detect_layout (h1+kicker+speaker→Title, Grid with metrics→metrics-N, Grid cols→Grid2/3/4, else Content)
```

## Node types

| Type | Source | HTML output |
|------|--------|------------|
| `Heading` | `# Title` / `## Section` | `<h1>` / `<h2>` |
| `Paragraph` | plain text | `<p>` |
| `Grid` | `::: grid {cols=N, class="X"}` | `<div class="grid X" style="grid-template-columns: repeat(N, 1fr)">` |
| `Card` | `::: card {tag="green"}` / `::: card {metric}` | `<div class="card tag-green"><h3>...</h3><p>...</p></div>` — metric sets `class_="metric"`, first line → header |
| `Table` | pipe tables | `<table><thead><tbody>` |
| `Quote` | `> text` | `<div class="quote">` |
| `ListNode` | `- item` | `<ul><li>` |
| `AttrNode` | `@kicker text` / `@speaker name=X role=Y` / `@contributor name=X role=Y` | `<div class="kicker">` / `<div class="speaker">` / `<div class="speaker contributor">` |
| `Inline::Text` | text | escaped text |
| `Inline::CodeSpan` | `` `code` `` | `<code>` |
| `Inline::SoftBreak` | line break | space |

## Key design decisions

- **Fenced blocks are pre-processed, not markdown-it plugins.** `::: card` and `::: grid` are extracted before markdown parsing, replaced with ◊FENCE_N markers, then re-inserted. This avoids writing a custom markdown-it plugin and handles nesting naturally via recursion.
- **Directives use HTML comment markers.** `@kicker text` becomes `<!--attr:kicker:text-->` which markdown-it treats as an HTML block. Post-processing converts these to AttrNode. This avoids custom inline parsing.
- **CSS is raw passthrough.** The `style:` frontmatter block is injected directly into `<style>`. No CSS parser. The browser (or weasyprint) handles everything. tinycss2 is used ONLY for extracting theme colors for PPTX.
- **Card auto-grouping.** Two or more consecutive `::: card` blocks without a `::: grid` wrapper are automatically wrapped in a Grid with cols=N. This simplifies the markdown syntax.
- **Jinja2 templates.** Both shell.html and presenter.html use Jinja2. CSS injection uses plain text placeholders (SLIDE_W, THEME_CSS, LOGO_CSS) replaced by Python before Jinja2 processes the template, avoiding escaping conflicts.
- **Bidirectional presenter sync.** `window.slidrCurrent` is an `Object.defineProperty` setter that calls `show()`. The presenter polls `window.opener.slidrCurrent` every 300ms. Clicking the presenter's main slide advances both windows.
- **Print CSS in base.css.** `@media print` resets absolute positioning from screen mode. `@page { size: Wpx Hpx; margin: 0 }` sets page dimensions for weasyprint. `page-break-before: always` on sections.
- **Screen scaling via CSS transform.** `body > section` renders at native pixel size (e.g., 1280x720px), then scales to fit viewport via `transform: translate(-50%, -50%) scale(var(--s))` where `--s` is computed by JavaScript.
- **Subtitle extraction.** `build_ir` extracts `@subtitle` AttrNode immediately after the h2 heading and places it outside layout columns. `_render_slide` in html.py does the same for HTML-only path. This keeps subtitles tight to the heading via `h2 { margin-bottom: 0.15em }` (kubecon values; h2 also gets `padding-top: 0`) and sizes them 0.85em via `h2 + .subtitle`.
- **Title font size configurable.** `--title-h1-size` (default `3.5em`) and `--title-subtitle-size` (default `1.8em`) are CSS variables in base.css. Themes override them in `:root`.
- **Plot deps as optional-dependencies.** `seaborn` and `pillow` are in `[project.optional-dependencies] plot` for workspace inheritance. The `plot` dependency-group exists for CI. Both declared so `slidr[plot]` resolves via PEP 621 and `pdm install -G plot` works in CI.
- **Slide transitions.** `@transition <name>` directive per slide, `transition: <name>` in frontmatter for default. Supported: `fade`, `slide`, `zoom`, `flip`, `wipe`. Implemented via CSS `@keyframes` triggered by `.active` class. 0.4s duration, incoming-only.
- **Grid card variants.** `::: card {side-image}` sits beside content without affecting row sizing -- centered, no background/border.

## Template cascade

```
base.css (structural layout, screen/print rules)
  ↓
default.css (theme: colors, fonts, card/quote/table styling)
  ↓
user style: block (frontmatter overrides)
```

## File conventions

- `base.css` uses `SLIDE_W`, `SLIDE_H`, `THEME_CSS`, `LOGO_CSS` as text placeholders. Python replaces them before Jinja2.
- `shell.html` uses `{% include "slidr.js" %}` for shared JS.
- `presenter.html` has its own inline JS (different from main -- grid layout, sync polling, notes).
- ALL font sizes use `em` (relative to 18pt base on section). No `px` for text.
- Spacing uses `em` for consistency. Percentages converted: `10%` of 720px slide height = 72px / 18 = 4em.
- No double dashes (`--`) in prose. Use colons (`:`) or single dashes. Dashes in code (CSS, Python, CLI flags) are fine.

## Fenced blocks

Slidr supports multiple fenced block types for diagrams and visualizations:

| Language | Renderer | Description |
|----------|----------|-------------|
| `dot` | Graphviz `dot` | Directed graphs, record shapes, HTML-like labels |
| `mermaid` | Mermaid CLI | Flowcharts, sequence diagrams, Gantt charts |
| `seaborn` | matplotlib/seaborn | Statistical charts, bar plots, gauge charts |

Grid, card, and metric syntax uses `:::` fences (pre-processed, not markdown-it):

```
::: grid {cols=2, class="top-grid"}
::: card {tag="green"}
### Card Title
Card content with **markdown**
:::
::: card {tag="red"}
### Another Card
More content
:::
:::
```

Card/grid `{...}` attributes: bare words → CSS classes (`{metric}` → `.card.metric`),
`k=v` → `k-v` classes (`{tag=green}` → `.card.tag-green`). Grid: `cols=N`,
`class=name` used literally.

`::: card {metric}`: first line → h3 value, rest → p label. No `###` needed.
Consecutive metric cards auto-group, layout → `metrics-N`.

All fenced blocks support markdown inside via `_expand_markdown` which uses `markdown_it.renderInline` with `breaks: False`. Lucide icons work inside fenced content: `{icon:check cls=accent-primary}`.

Cards can contain nested content -- fenced code blocks, `::: grid`/`::: card`, lists, and images. Nested fences are recursively extracted via `extract_fenced` and stored in `Card.children` as AST nodes. Body text lines go through `_expand_markdown` (icons via `_expand_icons` → `renderInline`). List items (`- text`) inside cards produce `<ul>` HTML in the card body.

## Slide layouts

Built-in layouts set via `@layout <name>` on a slide:

| Layout | Behavior |
|--------|----------|
| `image-right` | Text left, image right. Splits at first image or `@col` marker |
| `image-left` | Image left, text right |
| `two-col` | Two text columns split at `@col` |
| `compare` | Card | arrow | card, with optional `::: notes` footer |
| `ecosystem` | Compact stacked content with small h3 labels, inline logo flow. Uses `p:has(img) { display: contents }` for natural image wrapping |

Layout-ecosystem specifics:
- h3 labels: small (`0.7em`), no `::after` underline
- Cards: reduced padding (`0.3em 0.5em`)
- Logo images: uniform `0.8em × 0.8em` with `object-fit: contain`
- `<p>` tags containing only images dissolve via `display: contents`, letting images flow inline and wrap naturally
- Grids inside rows: zero margin, tight gap

## Seaborn styles

The `seaborn_theme` frontmatter field accepts a seaborn palette name
(`Paired` default, `deep`, `muted`, `pastel`, etc.) or a slidr theme name
matching a CSS file in `slidr/themes/<name>.css`. CSS `:root` variables
are parsed and mapped to matplotlib rcParams (card bg → axes.facecolor,
foreground → text.color, accent → edgecolor, dimmed → tick colors, font).

Style modules in `slidr.seaborn_styles.<name>` take precedence over CSS
for themes needing rcParams not derivable from CSS variables (e.g. custom
palette overrides, special matplotlib settings).

### Custom chart authoring

For charts beyond seaborn's high-level API, use matplotlib directly. Theme
colors are available through rcParams -- no hex codes needed:

- `plt.rcParams["axes.facecolor"]` — card background
- `plt.rcParams["axes.edgecolor"]` — primary accent
- `plt.rcParams["text.color"]` — foreground text
- `plt.rcParams["xtick.color"]` — dimmed text

For slide-matching figure background: `ax.set_facecolor("none")` +
`fig.patch.set_facecolor(plt.rcParams["axes.facecolor"])`.

Semantic colors via `plt.get_cmap("Paired")`: `cmap(4.5/12)` muted red,
`cmap(2.5/12)` green, `cmap(0.5/12)` light blue neutral. Paired is the
default palette for all themes unless overridden.

## Testing

- Always add tests after implementing new features. Tests are mandatory, not optional.
- Place tests in `tests/test_<component>.py` where `<component>` matches the module name (e.g. `tests/test_odp.py` for `src/slidr/render/odp.py`, `tests/test_parser.py` for `src/slidr/parser/markdown.py`).
- If a feature spans multiple components, put tests in the file matching the primary component.
- Run `pdm run pytest` after writing tests to confirm they pass.
- Test naming: `test_<function_name>_<scenario>` (e.g. `test_merge_text_elements_separated_by_card`).
