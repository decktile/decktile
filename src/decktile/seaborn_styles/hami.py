# SPDX-FileCopyrightText: 2026 Reza Jelveh
#
# SPDX-License-Identifier: Apache-2.0

"""Seaborn/matplotlib style matching the HAMi diagrams (predictygraph theme ``hami``).

HAMi green #16a34a, blue #2563eb, text #1e293b, muted #64748b, border #cbd5e1.
"""

PALETTE = [
    "#16a34a",  # HAMi green
    "#2563eb",  # blue
    "#0891b2",  # cyan
    "#ca8a04",  # yellow
    "#7c3aed",  # purple
    "#dc2626",  # red
]

STYLE = {
    "seaborn_palette": PALETTE,
    "font.family": "sans-serif",
    "font.sans-serif": ["Source Sans 3", "Source Sans Pro", "Arial", "Helvetica", "Liberation Sans", "sans-serif"],
    "axes.facecolor": "#ffffff",
    "axes.edgecolor": "#cbd5e1",
    "axes.labelcolor": "#1e293b",
    "axes.titlecolor": "#1e293b",
    "text.color": "#1e293b",
    "figure.facecolor": "#ffffff",
    "xtick.color": "#64748b",
    "ytick.color": "#64748b",
    "grid.color": "#f1f5f9",
    "patch.edgecolor": "#16a34a",
}
