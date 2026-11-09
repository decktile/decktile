# SPDX-FileCopyrightText: 2026 Reza Jelveh
#
# SPDX-License-Identifier: Apache-2.0

"""Seaborn/matplotlib style for the KubeCon NA 2026 theme.

Colors from the Title slide: blue #113E82, magenta #D62293, green #2E9C68,
yellow #E8C400 (darkened #FFEE88 so it reads on white), navy #052243.
"""

PALETTE = [
    "#113E82",  # blue, primary
    "#D62293",  # magenta
    "#2E9C68",  # green
    "#E8C400",  # yellow
    "#40BE95",  # mint
    "#052243",  # navy
]

STYLE = {
    "seaborn_palette": PALETTE,
    "font.family": "sans-serif",
    "font.sans-serif": ["Roboto", "Arial", "Helvetica Neue", "sans-serif"],
    "axes.facecolor": "#ffffff",
    "axes.edgecolor": "#052243",
    "axes.labelcolor": "#052243",
    "axes.titlecolor": "#052243",
    "text.color": "#052243",
    "figure.facecolor": "#ffffff",
    "xtick.color": "#5A6F8E",
    "ytick.color": "#5A6F8E",
    "grid.color": "#E3F6FF",
    "patch.edgecolor": "#ffffff",
    "patch.force_edgecolor": True,
}
