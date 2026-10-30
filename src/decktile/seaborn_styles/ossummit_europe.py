"""Seaborn/matplotlib style for the Open Source Summit Europe theme.

Brand palette: coral #E05845, green #0DA89D, teal #0A5560,
light coral #E58570, dark navy #003841. Background #ffffff.
"""

PALETTE = [
    "#E05845",  # coral, primary accent
    "#0DA89D",  # green, secondary accent
    "#0A5560",  # teal
    "#E58570",  # light coral, gradient end
    "#003841",  # dark navy, contrast
]

STYLE = {
    "seaborn_palette": PALETTE,
    "font.family": "sans-serif",
    "font.sans-serif": ["Roboto", "Arial", "Helvetica Neue", "sans-serif"],
    "axes.facecolor": "#ffffff",
    "axes.edgecolor": "#003841",
    "axes.labelcolor": "#003841",
    "axes.titlecolor": "#003841",
    "text.color": "#003841",
    "figure.facecolor": "#ffffff",
    "xtick.color": "#4F6F73",
    "ytick.color": "#4F6F73",
    "grid.color": "#EDF5F4",
    "patch.edgecolor": "#ffffff",
    "patch.force_edgecolor": True,
}
