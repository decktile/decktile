# Configuration for the decktile documentation (Sphinx + MyST).
# Built and published to https://decktile.github.io/decktile/ by .github/workflows/docs.yml.

import os
import sys
from importlib.metadata import PackageNotFoundError, version as _version

sys.path.insert(0, os.path.abspath("../src"))

project = "decktile"
copyright = "2026, Reza Jelveh"
author = "Reza Jelveh"
try:
    release = _version("decktile")
except PackageNotFoundError:
    release = "dev"
version = release

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.githubpages",
    "myst_parser",
]
myst_enable_extensions = ["colon_fence"]
myst_heading_anchors = 3
suppress_warnings = ["myst.header", "myst.xref_missing"]

exclude_patterns = ["_build", "superpowers", "Thumbs.db", ".DS_Store"]
language = "en"

html_theme = "furo"
html_title = "decktile"
html_logo = "../assets/logo/decktile-mark.svg"
html_favicon = "../assets/logo/decktile-mark.svg"
html_theme_options = {
    "source_repository": "https://github.com/decktile/decktile",
    "source_branch": "master",
    "source_directory": "docs/",
}
