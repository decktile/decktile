from typer.testing import CliRunner

from slidr.cli import app


def test_build_pdf_and_odp_together(tmp_path):
    """--odp used to return before the --pdf step, silently skipping the PDF."""
    deck = tmp_path / "d.md"
    deck.write_text("---\ntitle: T\n---\n\n## Slide\n\nBody.\n")
    result = CliRunner().invoke(app, ["--pdf", "--odp", "--output-dir", str(tmp_path), str(deck)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "d.odp").stat().st_size > 0
    assert (tmp_path / "d.pdf").stat().st_size > 0
