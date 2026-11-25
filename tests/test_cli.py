# SPDX-FileCopyrightText: 2026 Reza Jelveh
#
# SPDX-License-Identifier: Apache-2.0

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
    assert sorted(ln.split()[1] for ln in result.output.splitlines() if ln.startswith("Wrote")) == [
        "dist/a.html",
        "dist/b.html",
        "sub/dist/c.html",
    ]


def test_main_failing_file_does_not_stop_the_rest(tmp_path):
    (tmp_path / "bad.md").write_text("---\ntitle: [bad\n---\n\n## X\n")
    (tmp_path / "good.md").write_text(DECK)
    result = CliRunner().invoke(
        app, ["-o", str(tmp_path / "out"), str(tmp_path / "bad.md"), str(tmp_path / "missing.md"), str(tmp_path / "good.md")]
    )
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


def _make_theme(tmp_path):
    from decktile.cli import theme_app

    result = CliRunner().invoke(theme_app, ["create", str(tmp_path / "themes" / "acme")])
    assert result.exit_code == 0, result.output
    css = tmp_path / "themes" / "acme" / "theme.css"
    css.write_text(css.read_text() + '\nsection { background-image: url("assets/bg.png"); }\n.acme-marker { color: red; }\n')
    return css


def test_theme_folder_from_frontmatter_replaces_theme_and_rebases_assets(tmp_path):
    """A theme folder's url("assets/...") must resolve from dist/, which sees the
    deck folder through symlinks: the path is rebased onto the deck folder."""
    _make_theme(tmp_path)
    deck = tmp_path / "d.deck.md"
    deck.write_text("---\ntheme: themes/acme\n---\n\n## Slide\n\nBody.\n")
    result = CliRunner().invoke(app, [str(deck)])
    assert result.exit_code == 0, result.output
    html = (tmp_path / "dist" / "d.html").read_text()
    assert ".acme-marker" in html
    assert 'url("themes/acme/assets/bg.png")' in html


def test_theme_option_overrides_frontmatter_theme(tmp_path):
    _make_theme(tmp_path)
    deck = tmp_path / "d.deck.md"
    deck.write_text("---\ntheme: kubecon_japan\n---\n\n## Slide\n")
    result = CliRunner().invoke(app, ["--theme", str(tmp_path / "themes" / "acme"), str(deck)])
    assert result.exit_code == 0, result.output
    html = (tmp_path / "dist" / "d.html").read_text()
    assert ".acme-marker" in html and "KubeCon" not in html


def test_theme_folder_outside_deck_folder_is_an_error(tmp_path):
    _make_theme(tmp_path)
    (tmp_path / "decks").mkdir()
    deck = tmp_path / "decks" / "d.deck.md"
    deck.write_text(DECK)
    result = CliRunner().invoke(app, ["--theme", str(tmp_path / "themes" / "acme"), str(deck)])
    assert result.exit_code == 1
    assert "must be inside the deck folder" in result.output


def test_theme_create_refuses_non_empty_folder(tmp_path):
    from decktile.cli import theme_app

    (tmp_path / "acme").mkdir()
    (tmp_path / "acme" / "theme.css").write_text("keep me")
    result = CliRunner().invoke(theme_app, ["create", str(tmp_path / "acme")])
    assert result.exit_code == 1
    assert (tmp_path / "acme" / "theme.css").read_text() == "keep me"


def test_created_theme_preview_deck_builds_against_its_folder(tmp_path):
    """The scaffold must be usable as-is: its preview deck selects the folder
    with `theme: .` and every block in it renders (no diagram fallback)."""
    from decktile.cli import theme_app

    folder = tmp_path / "acme"
    assert CliRunner().invoke(theme_app, ["create", str(folder)]).exit_code == 0
    css = folder / "theme.css"
    css.write_text(css.read_text() + "\n.acme-marker { color: red; }\n")
    result = CliRunner().invoke(app, [str(folder / "preview.deck.md")])
    assert result.exit_code == 0, result.output
    html = (folder / "dist" / "preview.html").read_text()
    assert ".acme-marker" in html
    assert "pdg-fallback" not in html
