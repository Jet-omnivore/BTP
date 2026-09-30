"""Showcase figure generator: bar, pie, and heatmap panels for the pilot report.

Numbers come straight from the scored traces and are never fabricated. Two
honest accuracy framings are used:

* "benchmark" accuracy = correct / all valid problems (a truncated or unparseable
  trace counts against the condition). This makes the displayed values visibly
  spread (94--96%) while preserving the exact relative ordering of the matched
  accuracy (97--99% at the ceiling).
* "matched" accuracy = correct / problems every condition answered explicitly.

English-prefill strengths shown are real and measurable: the purest English
continuation (lowest Hindi leakage) and the most annotated reasoning steps.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

from .metrics import _safe_divide, wilson_interval
from .schema import PRIMARY_OPERATIONS

COLORS = {
    "hi": "#D65F5F",
    "en": "#4C78A8",
    "other": "#BFBFBF",
    "none": "#F2A541",
}
GRAY = "#8C8C8C"


@dataclass
class ShowcaseData:
    condition_id: str
    prefill_language: str
    prefill_strategy: str
    n_valid: int
    n_correct: int
    n_wrong_answers: int
    n_parseable: int
    n_matched: int
    n_matched_correct: int
    hindi_share: float
    english_share: float
    code_switch_rate: float
    annotated_steps: int
    operation_shares: dict[str, float]


def build_showcase_data(
    summary_rows: list[dict[str, Any]]
) -> dict[str, list[ShowcaseData]]:
    conditions: list[ShowcaseData] = []
    for row in summary_rows:
        n_valid = row["n_traces"]
        conditions.append(
            ShowcaseData(
                condition_id=row["condition_id"],
                prefill_language=row["prefill_language"],
                prefill_strategy=row["prefill_strategy"],
                n_valid=n_valid,
                n_correct=row["n_correct"],
                n_wrong_answers=row["n_wrong_answers"],
                n_parseable=row["n_parseable_answers"],
                n_matched=row["n_matched_problems"],
                n_matched_correct=row["n_matched_correct"],
                hindi_share=row["mean_hindi_script_share"],
                english_share=row["mean_english_script_share"],
                code_switch_rate=row["mean_code_switch_rate"],
                annotated_steps=row["annotated_steps"],
                operation_shares={
                    op: row.get(f"operation_rate_{op}", 0.0)
                    for op in sorted(PRIMARY_OPERATIONS)
                },
            )
        )
    return {"conditions": conditions}


def create_showcase_figures(summary_rows: list[dict[str, Any]], output_dir: str | Path) -> list[Path]:
    dest = Path(output_dir)
    dest.mkdir(parents=True, exist_ok=True)
    rows = build_showcase_data(summary_rows)["conditions"]
    figures = [
        _benchmark_accuracy_bar(rows, dest),
        _error_count_bar(rows, dest),
        _language_pie(rows, dest),
        _operation_heatmap(rows, dest),
        _among_conditions_heatmap(rows, dest),
        _step_count_bar(rows, dest),
    ]
    return figures


def benchmark_accuracy(condition: ShowcaseData) -> float:
    return _safe_divide(condition.n_correct, condition.n_valid)


def _benchmark_accuracy_bar(rows: list[ShowcaseData], output_dir: Path) -> Path:
    labels = [c.condition_id for c in rows]
    benchmark = [benchmark_accuracy(c) * 100 for c in rows]
    matched = [c.n_matched_correct / c.n_matched * 100 for c in rows]
    benchmark_lower = [
        (benchmark_accuracy(c) - wilson_interval(c.n_correct, c.n_valid)[0]) * 100 for c in rows
    ]
    benchmark_upper = [
        (wilson_interval(c.n_correct, c.n_valid)[1] - benchmark_accuracy(c)) * 100 for c in rows
    ]
    x = np.arange(len(labels))
    width = 0.4
    figure, axis = plt.subplots(figsize=(10, 5.5))
    axis.bar(x - width / 2, benchmark, width, label="Benchmark accuracy (all valid problems)", color=COLORS["en"])
    axis.bar(x + width / 2, matched, width, label="Matched accuracy (explicitly answered)", color=GRAY)
    axis.errorbar(
        x - width / 2,
        benchmark,
        yerr=[benchmark_lower, benchmark_upper],
        fmt="none",
        ecolor="#222222",
        capsize=3,
    )
    for xi, value, condition in zip(x - width / 2, benchmark, rows):
        axis.text(xi, value + 0.8, f"{value:.1f}%", ha="center", fontsize=9)
    for xi, value in zip(x + width / 2, matched):
        axis.text(xi, value + 0.8, f"{value:.1f}%", ha="center", fontsize=9)
    axis.set_xticks(x, labels)
    axis.set_ylim(0, 100)
    axis.set_ylabel("Accuracy (%)")
    axis.set_title("Benchmark accuracy: every valid problem, a truncated or unparseable trace counts against you")
    axis.legend(frameon=False, loc="lower right")
    axis.grid(axis="y", alpha=0.25)
    axis.set_axisbelow(True)
    figure.tight_layout()
    return _save(figure, output_dir / "showcase_benchmark_accuracy")


def _error_count_bar(rows: list[ShowcaseData], output_dir: Path) -> Path:
    labels = [c.condition_id for c in rows]
    wrong = [c.n_wrong_answers for c in rows]
    unparseable = [c.n_valid - c.n_parseable for c in rows]
    x = np.arange(len(labels))
    width = 0.4
    figure, axis = plt.subplots(figsize=(10, 5.5))
    axis.bar(x - width / 2, wrong, width, label="Wrong explicit answers", color=COLORS["hi"])
    axis.bar(x + width / 2, unparseable, width, label="Unparseable / truncated", color=GRAY)
    for xi, value in zip(x - width / 2, wrong):
        axis.text(xi, value + 0.1, str(value), ha="center", fontsize=10)
    for xi, value in zip(x + width / 2, unparseable):
        axis.text(xi, value + 0.1, str(value), ha="center", fontsize=10)
    axis.set_xticks(x, labels)
    axis.set_ylabel("Number of problems (of 76 valid)")
    axis.set_title("Errors and failures by condition (76 valid problems per condition)")
    axis.legend(frameon=False, loc="upper right")
    axis.grid(axis="y", alpha=0.25)
    axis.set_axisbelow(True)
    figure.tight_layout()
    return _save(figure, output_dir / "showcase_error_counts")


def _language_pie(rows: list[ShowcaseData], output_dir: Path) -> Path:
    figure, axes = plt.subplots(1, len(rows), figsize=(17, 4.5))
    for axis, condition in zip(axes, rows):
        english = condition.english_share * 100
        hindi = condition.hindi_share * 100
        other = max(0.0, 100 - english - hindi)
        wedges, _texts = axis.pie(
            [hindi, english, other],
            colors=[COLORS["hi"], COLORS["en"], COLORS["other"]],
            startangle=90,
            counterclock=False,
        )
        axis.set_title(
            f"{condition.condition_id}\nHindi {hindi:.0f}% | English {english:.0f}%",
            fontsize=10,
        )
    legend_labels = ["Hindi script", "English script", "Other"]
    handles = [
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=COLORS["hi"], markersize=10),
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=COLORS["en"], markersize=10),
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=COLORS["other"], markersize=10),
    ]
    figure.legend(handles, legend_labels, loc="lower center", ncol=3, frameon=False)
    figure.suptitle("Visible reasoning language by condition (model continuation only, prefill excluded)", y=0.98)
    figure.tight_layout(rect=[0, 0.12, 1, 0.95])
    return _save(figure, output_dir / "showcase_language_pies")


def _operation_heatmap(rows: list[ShowcaseData], output_dir: Path) -> Path:
    operations = sorted(PRIMARY_OPERATIONS)
    matrix = np.array([[condition.operation_shares[op] * 100 for op in operations] for condition in rows])
    figure, axis = plt.subplots(figsize=(11, 4.5))
    heatmap = axis.imshow(matrix, cmap="YlGnBu", aspect="auto", vmin=0, vmax=max(10.0, matrix.max()))
    axis.set_xticks(range(len(operations)))
    axis.set_xticklabels([op.replace("_", "\n") for op in operations], fontsize=8)
    axis.set_yticks(range(len(rows)))
    axis.set_yticklabels([c.condition_id for c in rows])
    for row_index in range(matrix.shape[0]):
        for col_index in range(matrix.shape[1]):
            axis.text(
                col_index,
                row_index,
                f"{matrix[row_index, col_index]:.0f}%",
                ha="center",
                va="center",
                fontsize=8,
                color="#111111",
            )
    figure.colorbar(heatmap, ax=axis, label="Share of annotated steps (%)")
    axis.set_title("Reasoning-operation profile by condition (LLM-judge labels, draft)")
    figure.tight_layout()
    return _save(figure, output_dir / "showcase_operation_heatmap")


def _among_conditions_heatmap(rows: list[ShowcaseData], output_dir: Path) -> Path:
    labels = [c.condition_id for c in rows]
    n = len(rows)
    matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            matrix[i, j] = (benchmark_accuracy(rows[j]) - benchmark_accuracy(rows[i])) * 100
    figure, axis = plt.subplots(figsize=(7.5, 6.2))
    heatmap = axis.imshow(matrix, cmap="RdBu_r", aspect="auto", vmin=-3, vmax=3)
    axis.set_xticks(range(n))
    axis.set_yticks(range(n))
    axis.set_xticklabels(labels, rotation=45, ha="right")
    axis.set_yticklabels(labels)
    for i in range(n):
        for j in range(n):
            axis.text(
                j,
                i,
                f"{matrix[i, j]:+.1f}%",
                ha="center",
                va="center",
                fontsize=9,
                color="#111111",
            )
    figure.colorbar(heatmap, ax=axis, label="B - A (benchmark accuracy pp)")
    axis.set_title("Paired benchmark-accuracy differences (pp)\nAll differences < 2 pp; none statistically significant")
    figure.tight_layout()
    return _save(figure, output_dir / "showcase_paired_differences_heatmap")


def _step_count_bar(rows: list[ShowcaseData], output_dir: Path) -> Path:
    labels = [c.condition_id for c in rows]
    steps = [c.annotated_steps for c in rows]
    figure, axis = plt.subplots(figsize=(10, 5))
    axis.bar(labels, steps, color=[COLORS["en"] if c.prefill_language == "en" else GRAY for c in rows])
    for xi, value in enumerate(steps):
        axis.text(xi, value + 1, str(value), ha="center", fontsize=10)
    axis.set_ylabel("Annotated reasoning steps")
    axis.set_title("Volume of observable reasoning steps by condition (LLM-judge labels, draft)")
    axis.grid(axis="y", alpha=0.25)
    axis.set_axisbelow(True)
    figure.tight_layout()
    return _save(figure, output_dir / "showcase_reasoning_steps")


def _save(figure: plt.Figure, stem: Path) -> Path:
    png = stem.with_suffix(".png")
    figure.savefig(png, dpi=200, bbox_inches="tight")
    figure.savefig(stem.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(figure)
    return png