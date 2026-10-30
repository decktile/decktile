"""PDF renderer using weasyprint."""

from pathlib import Path


def render(html_path: Path, output_path: Path, optimize_images: bool = False) -> None:
    from weasyprint import HTML  # lazy: needs system Pango, only for PDF/ODP output

    if optimize_images:
        HTML(filename=str(html_path)).write_pdf(
            target=str(output_path),
            jpeg_quality=85,
            optimize_images=True,
            dpi=200,
        )
    else:
        HTML(filename=str(html_path)).write_pdf(target=str(output_path))
