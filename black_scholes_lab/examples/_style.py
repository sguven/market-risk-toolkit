"""Shared matplotlib styling for the examples (validated categorical palette)."""

from __future__ import annotations

import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# Make the package importable when examples are run from any directory.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

FIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "figures")
os.makedirs(FIG_DIR, exist_ok=True)

# Fixed-order categorical palette (colour-vision-deficiency validated).
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
TEXT = "#1f1f1e"
MUTED = "#6b6a66"
GRID = "#e4e3df"

plt.rcParams.update(
    {
        "figure.dpi": 130,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": GRID,
        "axes.labelcolor": TEXT,
        "axes.titleweight": "bold",
        "axes.titlesize": 11,
        "axes.labelsize": 9.5,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.labelsize": 8.5,
        "ytick.labelsize": 8.5,
        "legend.frameon": False,
        "legend.fontsize": 8.5,
        "lines.linewidth": 2.0,
        "font.family": "DejaVu Sans",
        "axes.prop_cycle": matplotlib.cycler(color=SERIES),
    }
)


def save(fig, name: str) -> str:
    path = os.path.join(FIG_DIR, name)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return os.path.relpath(path, os.path.join(FIG_DIR, ".."))
