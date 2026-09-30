"""Presentation-ready figures generated from analysis tables."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt

from .schema import PRIMARY_OPERATIONS

COLORS = {
    "hi": "#D65F5F",
    "en": "#4C78A8",
    "none": "#8C8C8C",
    "neutral": "#72B7B2",
    "planning": "#F2A541",
    "verification": "#9C6ADE",
}


def create_figures(summary: list[dict[str, Any]], output_dir: str | Path) -> list[Path]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    if not summary:
        return []
    figures = [
        _accuracy_figure(summary, destination),
        _parseability_figure(summary, destination),
        _language_figure(summary, destination),
    ]
    if any(row["annotated_steps"] for row in summary):
        figures.append(_operation_figure(summary, destination))
    return figures


def _accuracy_figure(summary: list[dict[str, Any]], output_dir: Path) -> Path:
    labels = [row["condition_id"] for row in summary]
    values = [row["matched_accuracy"] * 100 for row in summary]
    lower = [
        (row["matched_accuracy"] - row["matched_accuracy_ci_low"]) * 100 for row in summary
    ]
    upper = [
        (row["matched_accuracy_ci_high"] - row["matched_accuracy"]) * 100 for row in summary
    ]
    figure, axis = plt.subplots(figsize=(10, 5.5))
    axis.bar(labels, values, color=[COLORS.get(row["prefill_strategy"], "#8C8C8C") for row in summary])
    axis.errorbar(labels, values, yerr=[lower, upper], fmt="none", ecolor="#222222", capsize=4)
    axis.set_ylim(0, 100)
    axis.set_ylabel("Matched accuracy (%)")
    axis.set_title("Accuracy on problems solved explicitly in every condition")
    axis.grid(axis="y", alpha=0.25)
    axis.set_axisbelow(True)
    figure.tight_layout()
    return _save(figure, output_dir / "accuracy_by_condition")


def _language_figure(summary: list[dict[str, Any]], output_dir: Path) -> Path:
    labels = [row["condition_id"] for row in summary]
    hindi = [row["mean_hindi_script_share"] * 100 for row in summary]
    english = [row["mean_english_script_share"] * 100 for row in summary]
    figure, axis = plt.subplots(figsize=(10, 5.5))
    axis.bar(labels, hindi, label="Devanagari/Hindi script", color=COLORS["hi"])
    axis.bar(labels, english, bottom=hindi, label="Latin/English script", color=COLORS["en"])
    axis.set_ylim(0, 100)
    axis.set_ylabel("Share of visible script characters (%)")
    axis.set_title("Model-continuation language composition (prefill excluded)")
    axis.legend(frameon=False, loc="upper right")
    axis.grid(axis="y", alpha=0.25)
    axis.set_axisbelow(True)
    figure.tight_layout()
    return _save(figure, output_dir / "reasoning_language_composition")


def _parseability_figure(summary: list[dict[str, Any]], output_dir: Path) -> Path:
    labels = [row["condition_id"] for row in summary]
    values = [row["answer_parse_rate"] * 100 for row in summary]
    figure, axis = plt.subplots(figsize=(10, 5.5))
    axis.bar(labels, values, color="#8C8C8C")
    axis.set_ylim(0, 100)
    axis.set_ylabel("Explicit final-answer marker rate (%)")
    axis.set_title("Answer-format completion by condition")
    axis.grid(axis="y", alpha=0.25)
    axis.set_axisbelow(True)
    figure.tight_layout()
    return _save(figure, output_dir / "answer_parse_rate")


def _operation_figure(summary: list[dict[str, Any]], output_dir: Path) -> Path:
    labels = [row["condition_id"] for row in summary]
    figure, axis = plt.subplots(figsize=(11, 6))
    bottom = [0.0] * len(summary)
    palette = plt.get_cmap("tab20")
    for index, operation in enumerate(sorted(PRIMARY_OPERATIONS)):
        values = [row.get(f"operation_rate_{operation}", 0.0) * 100 for row in summary]
        if not any(values):
            continue
        axis.bar(labels, values, bottom=bottom, label=operation.replace("_", " "), color=palette(index))
        bottom = [current + value for current, value in zip(bottom, values)]
    axis.set_ylim(0, 100)
    axis.set_ylabel("Share of annotated steps (%)")
    axis.set_title("Observable reasoning-operation distribution")
    axis.legend(frameon=False, bbox_to_anchor=(1.02, 1), loc="upper left")
    axis.grid(axis="y", alpha=0.25)
    axis.set_axisbelow(True)
    figure.tight_layout()
    return _save(figure, output_dir / "reasoning_operation_distribution")


def _save(figure: plt.Figure, stem: Path) -> Path:
    png = stem.with_suffix(".png")
    figure.savefig(png, dpi=200, bbox_inches="tight")
    figure.savefig(stem.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(figure)
    return png
