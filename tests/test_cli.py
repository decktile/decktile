from typer.testing import CliRunner

from decktile.cli import app


def test_build_pdf_and_odp_together(tmp_path):
    """--odp used to return before the --pdf step, silently skipping the PDF."""
    deck = tmp_path / "d.md"
    deck.write_text("---\ntitle: T\n---\n\n## Slide\n\nBody.\n")
    result = CliRunner().invoke(app, ["--pdf", "--odp", "--output-dir", str(tmp_path), str(deck)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "d.odp").stat().st_size > 0
    assert (tmp_path / "d.pdf").stat().st_size > 0


DECK = "---\ntitle: T\n---\n\n## Slide\n\nBody.\n"


def test_main_missing_file_reports_error_and_exits_1(tmp_path):
    result = CliRunner().invoke(app, [str(tmp_path / "nope.md")])
    assert result.exit_code == 1
    assert "nope.md: no such file" in result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)


def test_main_quoted_glob_builds_each_deck_once(tmp_path, monkeypatch):
    """'**/*.md' must not rebuild decks reached again through the source
    symlinks decktile puts in every dist/ dir."""
    (tmp_path / "sub").mkdir()
    for p in ("a.md", "b.md", "sub/c.md"):
        (tmp_path / p).write_text(DECK)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(app, ["**/*.md"]).exit_code == 0  # creates dist/ symlinks
    result = runner.invoke(app, ["**/*.md"])
    assert result.exit_code == 0, result.output
    assert sorted(l.split()[1] for l in result.output.splitlines() if l.startswith("Wrote")) == [
        "dist/a.html", "dist/b.html", "sub/dist/c.html"]


def test_main_failing_file_does_not_stop_the_rest(tmp_path):
    (tmp_path / "bad.md").write_text("---\ntitle: [bad\n---\n\n## X\n")
    (tmp_path / "good.md").write_text(DECK)
    result = CliRunner().invoke(app, ["-o", str(tmp_path / "out"),
                                      str(tmp_path / "bad.md"), str(tmp_path / "missing.md"),
                                      str(tmp_path / "good.md")])
    assert result.exit_code == 1
    assert "bad.md:" in result.output and "missing.md: no such file" in result.output
    assert (tmp_path / "out" / "good.html").exists()


def test_seaborn_theme_without_chart_libraries(monkeypatch):
    """seaborn_theme in frontmatter must not crash a build when matplotlib isn't installed."""
    import builtins

    from decktile.render import seaborn as sb

    real_import = builtins.__import__

    def no_plot(name, *a, **k):
        if name.split(".")[0] in ("matplotlib", "seaborn"):
            raise ImportError(name)
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", no_plot)
    sb.set_theme("default")  # must not raise
