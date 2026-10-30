# Vendored: Lucide icon font

Source: https://www.npmjs.com/package/lucide-static (npm), version 1.61.0.
License: ISC (same as Lucide itself).

Files:
- `lucide.ttf` -- icon glyphs, one Lucide icon per private-use-area Unicode
  codepoint.
- `lucide.css` -- `.icon-<name>::before { content: "\eXXX"; }` codepoint
  map, parsed at runtime to resolve an icon name to its glyph.

Fetched via `npm install lucide-static@1.61.0` and copied from
`node_modules/lucide-static/font/`. Tracked via git-lfs (`*.ttf` in
`.gitattributes`) to avoid bloating the regular git object store with the
~900KB binary.

Used by the ODP renderer to embed lucide icons as colored font glyphs
(`style:font-face` + embedded font data in the package) instead of
per-icon SVG image frames -- a font glyph picks up `fo:color` like any
other text run, matching the HTML's themed icon color, and scales with
font-size instead of a fixed pixel box.
