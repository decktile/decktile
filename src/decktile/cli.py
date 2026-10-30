"""decktile CLI entry point."""

import glob
import time
from pathlib import Path
from typing import Optional

import typer

from decktile.parser.markdown import parse
from decktile.render.html import render as render_html, default_theme, load_theme, base_css
from decktile.render.ir import assemble_css
from decktile.render.odp import render as render_odp
from decktile.render.pdf import render as render_pdf

app = typer.Typer(help="Markdown to styled HTML + ODP + PDF", no_args_is_help=True)


@app.callback(invoke_without_command=True)
def main(
    files: Optional[list[Path]] = typer.Argument(None, help="Markdown files to build; globs like '*.md' or 'talks/**/*.md' are expanded"),
    output_dir: Optional[Path] = typer.Option(None, "-o", "--output-dir", help="Output directory (default: <input>/dist/)"),
    pdf: bool = typer.Option(False, "--pdf", help="Generate PDF"),
    odp: bool = typer.Option(False, "--odp", help="Generate ODP (programmatic)"),
    image_odp: bool = typer.Option(False, "--image-odp", help="Generate ODP (PDF screenshots)"),
    dist: bool = typer.Option(False, "--dist", help="Package HTML + referenced assets into a zip"),
    optimize_images: bool = typer.Option(False, "--optimize-images/--no-optimize-images", help="Optimize images in PDF output (jpeg_quality=85, dpi=150)"),
    watch: bool = typer.Option(False, "-w", "--watch", help="Watch file and rebuild on changes"),
    debug: bool = typer.Option(False, "--debug", help="Dump AST + write debug CSS"),
    css: Optional[Path] = typer.Option(None, "--css", help="Custom CSS theme file (overrides default)"),
):
    if not files:
        raise typer.Exit()
    if css and not css.is_file():
        _error(css, "CSS file not found")
        raise typer.Exit(1)

    paths, missing = _expand(files)
    for f in missing:
        _error(f, "no files match" if any(c in str(f) for c in "*?[")
               else "not a file" if f.exists() else "no such file")

    if watch:
        _watch(paths, output_dir, pdf, odp, image_odp, debug, css)
        return

    failed = len(missing)
    for f in paths:
        try:
            _build(f, output_dir, pdf, odp, image_odp, dist, optimize_images, debug, css)
        except Exception as e:
            if debug:
                raise
            _error(f, e)
            failed += 1
    if failed:
        raise typer.Exit(1)


def _expand(args: list[Path]) -> tuple[list[Path], list[Path]]:
    """Expand glob patterns the shell left alone (quoted, or no match);
    keep order, drop duplicates. Returns (existing files, unmatched args).
    Duplicates are by resolved path: output dirs hold symlinks back to the
    source dirs, so '**/*.md' reaches each deck again through every dist/.
    The real (non-symlinked) path wins, so output lands next to it."""
    paths: list[Path] = []
    seen: set[Path] = set()
    missing: list[Path] = []
    for a in args:
        matches = ([Path(m) for m in glob.glob(str(a), recursive=True)]
                   if any(c in str(a) for c in "*?[") else [a])
        found = sorted((m for m in matches if m.is_file()),
                       key=lambda m: (m.resolve() != m.absolute(), str(m)))
        if not found:
            missing.append(a)
        for m in found:
            if m.resolve() not in seen:
                seen.add(m.resolve())
                paths.append(m)
    return paths, missing


def _error(path: Path, msg: object) -> None:
    typer.echo(f"error: {path}: {msg}", err=True)


def _build(file: Path, output_dir: Optional[Path], pdf: bool,
           odp: bool, image_odp: bool, dist: bool, optimize_images: bool,
           debug: bool, css_path: Optional[Path]) -> None:
    content = file.read_text(encoding="utf-8")
    doc = parse(content)
    dims = doc.meta.dimensions()

    out_dir = output_dir or file.parent / "dist"
    out_dir.mkdir(parents=True, exist_ok=True)
    _symlink_assets(file.parent, out_dir)
    stem = file.stem

    if doc.meta.theme and doc.meta.theme != "default":
        theme_css = load_theme(doc.meta.theme)
    else:
        theme_css = default_theme()
    if css_path and css_path.is_file():
        theme_css += "\n" + css_path.read_text(encoding="utf-8")
    theme_css += "\n" + (doc.meta.style or "")

    # Assemble CSS: base.css (with dims) + theme + logo + pygments
    css = assemble_css(base_css(), theme_css, dims, doc.meta.logo,
                       doc.meta.watermark, doc.meta.pygments_style or "default",
                       doc.meta.logo_dark, doc.meta.background)

    html = render_html(doc, theme_css, css, dims, doc.meta.logo)
    html_path = out_dir / f"{stem}.html"
    html_path.write_text(html, encoding="utf-8")
    typer.echo(f"Wrote {html_path} ({len(html)} bytes)")

    if dist:
        _make_dist(file.parent, out_dir, html_path, html, theme_css, stem)

    if debug:
        css = base_css().replace("SLIDE_W", str(dims[0])).replace("SLIDE_H", str(dims[1]))
        css = css.replace("THEME_CSS", theme_css)
        css = css.replace("LOGO_CSS", "").replace("{theme_css}", "").replace("{logo_css}", "")
        css_path = out_dir / f"{stem}.css"
        css_path.write_text(css, encoding="utf-8")
        typer.echo(f"Wrote {css_path} (debug CSS, {len(css)} bytes)")

    if odp:
        odp_path = out_dir / f"{stem}.odp"
        render_odp(doc, odp_path, base_css(), theme_css,
                   source_dir=file.parent)
        typer.echo(f"Wrote {odp_path} ({odp_path.stat().st_size} bytes)")

    if image_odp:
        img_path = out_dir / f"{stem}.odp"
        pdf_path = out_dir / f"{stem}.pdf"
        render_pdf(html_path, pdf_path)
        _pdf_to_odp(pdf_path, img_path, dims=dims)
        typer.echo(f"Wrote {img_path} ({img_path.stat().st_size} bytes)")
        return

    if pdf:
        pdf_path = out_dir / f"{stem}.pdf"
        render_pdf(html_path, pdf_path, optimize_images=optimize_images)
        typer.echo(f"Wrote {pdf_path} ({pdf_path.stat().st_size} bytes)")
        return

    typer.echo(f"Parsed {len(doc.slides)} slides")
    if debug:
        for i, slide in enumerate(doc.slides):
            typer.echo(f"  Slide {i+1}: {slide.layout} ({len(slide.children)} children)")
            for n in slide.children:
                typer.echo(f"    {type(n).__name__}: {_node_summary(n)}")


def _watch(files: list[Path], output_dir: Optional[Path], pdf: bool,
           odp: bool, image_odp: bool, debug: bool, css_path: Optional[Path]) -> None:
    if not files:
        raise typer.Exit(1)
    mtimes: dict[Path, float] = {}
    typer.echo(f"Watching {len(files)} file(s) for changes (Ctrl+C to stop)")

    while True:
        try:
            for f in files:
                try:
                    mtime = f.stat().st_mtime
                except FileNotFoundError:
                    continue  # mid-save rename or deleted: pick it up when it's back
                if mtimes.get(f) != mtime:
                    mtimes[f] = mtime
                    typer.echo("---")
                    try:
                        _build(f, output_dir, pdf, odp, image_odp, False, False, debug, css_path)
                    except Exception as e:
                        _error(f, e)
            time.sleep(1)
        except KeyboardInterrupt:
            typer.echo("\nStopped watching.")
            break


def _pdf_to_odp(pdf_path: Path, output_path: Path, dims: tuple[int, int]) -> None:
    import os, subprocess, tempfile
    from odfdo import Document, DrawPage, Frame

    sw, sh = dims
    odp = Document("presentation")
    odp.body.clear()

    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            ["pdftoppm", "-png", "-r", "150", str(pdf_path), f"{tmp}/page"],
            capture_output=True, text=True, timeout=60,
        )
        for png_file in sorted(Path(tmp).glob("page-*.png")):
            i = int(png_file.stem.split("-")[1]) - 1
            page = DrawPage(f"slide{i + 1}", name=f"Slide {i + 1}")
            uri = odp.add_file(str(png_file))
            frame = Frame.image_frame(
                image=uri, text="",
                size=(f"{sw * 2.54 / 96:.2f}cm", f"{sh * 2.54 / 96:.2f}cm"),
                position=("0cm", "0cm"),
                anchor_type="page",
            )
            page.append(frame)
            odp.body.append(page)

    odp.save(str(output_path), pretty=True)


def _node_summary(node) -> str:
    from decktile.parser.ast import Heading, Table, Grid, AttrNode

    if isinstance(node, Heading):
        return f"L{node.level}: {node.content[0].content if node.content else ''}"
    elif isinstance(node, Table):
        return f"({len(node.headers)} cols x {len(node.rows)} rows)"
    elif isinstance(node, Grid):
        return f"cols={node.cols} children={len(node.children)}"
    elif isinstance(node, AttrNode):
        return f"{node.type}: {node.value}"
    return ""


def _symlink_assets(source_dir: Path, dist_dir: Path) -> None:
    """Symlink all directories from source to dist. Skips files and dist itself."""
    for item in source_dir.iterdir():
        if not item.is_dir():
            continue
        if item.name == dist_dir.name:
            continue
        dest = dist_dir / item.name
        if not dest.exists():
            dest.symlink_to(item.resolve())


def _make_dist(source_dir: Path, out_dir: Path, html_path: Path,
               html: str, theme_css: str, stem: str) -> None:
    import re, zipfile

    zip_path = out_dir / f"{stem}.zip"
    seen = set()

    with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(str(html_path), html_path.name)

        urls = set()
        for pattern in [r'src="([^"]+)"', r'href="([^"]+)"', r'url\(["\']?([^)"\']+)["\']?\)']:
            for m in re.finditer(pattern, html + theme_css):
                urls.add(m.group(1))

        for url in sorted(urls):
            if url.startswith(("http:", "https:", "data:", "#")):
                continue
            if url.startswith("/"):
                continue
            asset = source_dir / url
            if not asset.is_file():
                continue
            # Use real path for dedup, resolved symlink for actual file access
            real = asset.resolve()
            if str(real) in seen:
                continue
            seen.add(str(real))
            # Preserve original relative path structure in zip
            zf.write(str(real), url)

    typer.echo(f"Wrote {zip_path} ({zip_path.stat().st_size} bytes, {len(seen)} assets)")
