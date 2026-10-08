---
name: creating-slide-qr-codes
description: Use when a slidr deck needs a QR code (talk link, landing page, repo) on the title or closing slide, optionally with a project logo in the middle
---

# Creating slide QR codes

## Overview

Generate the PNG with `make_qr.py` (segno, error correction H so a centred logo stays scannable), save it under the event's brand folder, and show it with `@side-image`.

## Steps

1. Generate from the deck repo root:

   ```bash
   pdm run python slidr/skills/creating-slide-qr-codes/make_qr.py \
     https://go.dynamia.ai/observability-summit-europe \
     assets/brand/<event>/qr-code-<event>.png \
     --icon assets/hami-graph-color.png
   ```

   `--color` sets the module colour (default `#003841`, dark navy). `--icon-ratio` sets logo width (default 0.22).
2. Put it on the title and closing slides, one `@side-image` per slide, directly after `@variant dark` / before `@kicker`:

   ```markdown
   @variant dark
   @side-image assets/brand/<event>/qr-code-<event>.png
   @kicker ...
   ```

3. Rebuild (`pdm run slidr <deck>.md --pdf`) and look at page 1 and the last page. Scan it with a phone before the talk.

## Common mistakes

| Mistake | Fix |
|---|---|
| Logo wider than ~25% of the code, or error level below H | Stays unscannable; keep the defaults |
| Light module colour | Scanners need dark-on-light contrast |
| Overwriting a QR another deck uses | Each talk link gets its own file; check `grep -rn side-image *.md` first |
| Long text line on the closing slide runs under the QR | Break the line or shorten it |
| A second `@side-image` on one slide | Only one corner image per slide; it replaces the other |
