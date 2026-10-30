---
name: creating-conference-themes
description: Use when a decktile deck needs a new conference or event theme, a restyle from another event's theme, or brand assets (background, watermark, footer art, color palette) turned into a decktile stylesheet
---

# Creating conference themes for decktile

## Overview

A decktile theme is one CSS file in `src/decktile/themes/<name>.css`. Copy the closest existing theme and change values, not structure. Brand assets stay in the deck repository.

## Rules

- **Only file you add:** `src/decktile/themes/<name>.css`. Never edit `render/templates/base.css`.
- **Theme lookup is silent:** `load_theme` only reads `src/decktile/themes/`. A wrong `theme:` name renders with `default.css` and no error.
- **Assets stay with the deck:** reference them as `url("assets/brand/<event>/<file>")`, relative to the deck, as `ossummit_korea.css` does.
- **Colors go into existing variables only:** the four accents (`--color-accent`, `--color-accent-primary`, `--color-accent-secondary`, `--color-accent-contrast`) plus the `--tag-*-border` / `--tag-*-bg` pairs. Do not invent new variables.
- **Charts follow automatically:** `seaborn_theme: <name>` derives matplotlib colors from the CSS variables.

## Steps

1. Copy the closest theme, e.g. `cp src/decktile/themes/ossummit_korea.css src/decktile/themes/<name>.css`.
2. Map the palette: primary accent for headings' underline, list markers and links; secondary and contrast for icons and cards; tag borders from the palette (green, cyan, yellow, red slots).
3. Set three surfaces:
   - light slides: `section { background: ... }`
   - dark slides: `[data-theme="dark"] { ...variables... }` and `section[data-theme="dark"] { background: ... }`
   - title and section dividers: `section.layout-title, section.layout-title[data-theme="dark"] { background: ... }`. The doubled selector is required: title slides usually carry `@variant dark`, and the dark rule otherwise wins.
4. Place watermark, footer text and page number (see Quick reference).

## Quick reference

| Need | CSS |
|---|---|
| Gradient title background | `background: linear-gradient(180deg, #TOP 0%, #BOTTOM 100%);` |
| Footer art along the bottom | `background: var(--bg-image) right bottom / auto 6.5em no-repeat, var(--color-background);` |
| Watermark position | `section::after { left: ...; right: auto; bottom: 1em; width: 8em; height: 1.3em; background-position: left bottom; }` |
| No watermark on title/dark | `.layout-title::after, section[data-theme="dark"]::after { background-image: none; }` |
| Footer/page-number offsets | `footer` and `.slide-num` use `font-size: 0.6em`: write slide-relative offsets as `calc(1.1em / 0.6)` |

## Done means rendered and inspected

1. Copy an existing deck to `_preview_<name>.md` in the deck repo; set `theme:` and `seaborn_theme:` to `<name>`; delete its `watermark:` frontmatter line so the theme's watermark shows.
2. `python -m decktile --pdf --dist _preview_<name>.md`
3. `grep -c '<primary hex>' dist/_preview_<name>.html` must be non-zero (proves the theme loaded).
4. Rasterize and look at: title, section divider, card grid, table, chart, metrics:
   `python -c "import pymupdf; d=pymupdf.open('dist/_preview_<name>.pdf'); [d[i-1].get_pixmap(dpi=60).save(f'/tmp/p{i}.png') for i in (1,2,3,12)]"`
5. Delete `_preview_<name>.md` and its `dist/` outputs.

## Common mistakes

| Symptom | Cause | Fix |
|---|---|---|
| Deck looks like the default theme | Theme name typo or file outside `src/decktile/themes/` | Check step 3 of "Done" |
| Title slide shows dark background, not the title gradient | `section[data-theme="dark"]` outranks `.layout-title` | Use the doubled title selector |
| Footer ornament covers cards and tables | Footer art sized by width (`100% auto`) | Size by height (`auto 6.5em`) |
| Footer text lands in the wrong place | Offsets written in slide `em`, applied at `0.6em` | Divide by 0.6 |
