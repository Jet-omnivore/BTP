"""Generate showcase figures (table, bars, pies, heatmaps) for the MMLU condition run.

Numbers come from the scored traces and analysed summary; nothing is fabricated or
re-weighted. Unlike the pilot showcase (ceiling near 100%), MMLU accuracies spread
widely, so the paired-difference heatmap uses a real scale centred on 0 with the
McNemar p-value annotated on each cell.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hrp.io import read_jsonl  # noqa: E402
from hrp.metrics import wilson_interval  # noqa: E402

SCORED = ROOT / "data" / "traces" / "groq_mmlu_scored.jsonl"
PROBLEMS = ROOT / "data" / "processed" / "mmlu_problems.jsonl"
SUMMARY = ROOT / "outputs" / "mmlu" / "summary.json"
OUTPUT_DIR = ROOT / "outputs" / "mmlu" / "showcase"

COLORS = {"hi": "#D65F5F", "en": "#4C78A8", "other": "#BFBFBF", "none": "#F2A541"}
GRAY = "#8C8C8C"

GREEN = "#2E8B57"
RED = "#C0392B"
AMBER = "#E6B800"


def _save(figure: plt.Figure, stem: Path) -> Path:
    png = stem.with_suffix(".png")
    figure.savefig(png, dpi=200, bbox_inches="tight")
    figure.savefig(stem.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(figure)
    return png


def load_data() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    traces = read_jsonl(SCORED)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    return traces, summary


def _summary_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
    return summary["conditions"]


def _condition_order(rows: list[dict[str, Any]]) -> list[str]:
    return [row["condition_id"] for row in rows]


def table_image(rows: list[dict[str, Any]], dest: Path) -> Path:
    columns = [
        ("condition_id", "Condition"),
        ("n_traces", "Valid"),
        ("n_parseable_answers", "Explicit"),
        ("n_correct", "Correct"),
        ("n_wrong_answers", "Wrong"),
        ("n_unparseable", "Unparseable"),
        ("answer_parse_rate", "Parse %"),
        ("accuracy", "Accuracy %"),
        ("matched_accuracy", "Matched %"),
        ("mean_hindi_script_share", "Hindi %"),
        ("mean_english_script_share", "English %"),
    ]
    data = [[str(row[field] * 100)[:4] if field in {"answer_parse_rate", "accuracy", "matched_accuracy", "mean_hindi_script_share", "mean_english_script_share"} else str(row[field]) for field, _name in columns] for row in rows]
    headers = [name for _field, name in columns]
    figure, axis = plt.subplots(figsize=(11, 0.9 + 0.45 * len(rows)))
    axis.axis("off")
    table = axis.table(
        cellText=data,
        colLabels=headers,
        cellLoc="center",
        loc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.5)
    for (row_index, _col_index), cell in table.get_celld().items():
        if row_index == 0:
            cell.set_facecolor("#4C78A8")
            cell.set_text_props(color="white", fontweight="bold")
        elif row_index % 2 == 0:
            cell.set_facecolor("#F2F6FB")
    axis.set_title(
        "MMLU condition summary (33 problems x 4 conditions)\nUnparseable counts against parse rate; matched = problems every condition answered explicitly",
        fontsize=10,
    )
    figure.tight_layout(rect=[0, 0.05, 1, 0.85])
    return _save(figure, dest / "mmlu_summary_table")


def accuracy_bar(rows: list[dict[str, Any]], dest: Path) -> Path:
    labels = [row["condition_id"] for row in rows]
    benchmark = [row["n_correct"] / row["n_traces"] * 100 for row in rows]
    matched = [
        row["n_matched_correct"] / row["n_matched_problems"] * 100 if row["n_matched_problems"] else 0.0
        for row in rows
    ]
    lower = [
        (row["n_correct"] / row["n_traces"] - wilson_interval(row["n_correct"], row["n_traces"])[0]) * 100
        for row in rows
    ]
    upper = [
        (wilson_interval(row["n_correct"], row["n_traces"])[1] - row["n_correct"] / row["n_traces"]) * 100
        for row in rows
    ]
    x = np.arange(len(labels))
    width = 0.4
    figure, axis = plt.subplots(figsize=(10, 5.5))
    axis.bar(x - width / 2, benchmark, width, label="Accuracy (all 33 traces)", color=COLORS["en"])
    axis.bar(x + width / 2, matched, width, label="Matched accuracy", color=GRAY)
    axis.errorbar(x - width / 2, benchmark, yerr=[lower, upper], fmt="none", ecolor="#222222", capsize=3)
    for xi, value in zip(x - width / 2, benchmark):
        axis.text(xi, value + 0.8, f"{value:.1f}%", ha="center", fontsize=9)
    for xi, value in zip(x + width / 2, matched):
        axis.text(xi, value + 0.8, f"{value:.1f}%", ha="center", fontsize=9)
    axis.set_xticks(x, labels)
    axis.set_ylim(0, 100)
    axis.set_ylabel("Accuracy (%)")
    axis.set_title("MMLU accuracy by condition\nAccuracy = correct / 33 traces; unparseable counts against you")
    axis.legend(frameon=False, loc="lower right")
    axis.grid(axis="y", alpha=0.25)
    axis.set_axisbelow(True)
    figure.tight_layout()
    return _save(figure, dest / "mmlu_accuracy_bar")


def error_counts_bar(rows: list[dict[str, Any]], dest: Path) -> Path:
    labels = [row["condition_id"] for row in rows]
    wrong = [row["n_wrong_answers"] for row in rows]
    unparseable = [row["n_unparseable"] for row in rows]
    x = np.arange(len(labels))
    figure, axis = plt.subplots(figsize=(10, 5.5))
    axis.bar(x - 0.2, wrong, 0.4, label="Wrong explicit answers", color=COLORS["hi"])
    axis.bar(x + 0.2, unparseable, 0.4, label="Unparseable / no answer", color=GRAY)
    for xi, value in zip(x - 0.2, wrong):
        axis.text(xi, value + 0.1, str(value), ha="center", fontsize=10)
    for xi, value in zip(x + 0.2, unparseable):
        axis.text(xi, value + 0.1, str(value), ha="center", fontsize=10)
    axis.set_xticks(x, labels)
    axis.set_ylabel("Number of traces (of 33 per condition)")
    axis.set_title("Wrong and unparseable counts by condition")
    axis.legend(frameon=False, loc="upper right")
    axis.grid(axis="y", alpha=0.25)
    axis.set_axisbelow(True)
    figure.tight_layout()
    return _save(figure, dest / "mmlu_error_counts_bar")


def language_pies(rows: list[dict[str, Any]], dest: Path) -> Path:
    figure, axes = plt.subplots(1, len(rows), figsize=(17, 4.5))
    for axis, row in zip(axes, rows):
        hindi = row["mean_hindi_script_share"] * 100
        english = row["mean_english_script_share"] * 100
        other = max(0.0, 100 - hindi - english)
        axis.pie(
            [hindi, english, other],
            colors=[COLORS["hi"], COLORS["en"], COLORS["other"]],
            startangle=90,
            counterclock=False,
        )
        axis.set_title(
            f"{row['condition_id']}\nHindi {hindi:.0f}% | English {english:.0f}%",
            fontsize=10,
        )
    handles = [
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=COLORS["hi"], markersize=10, label="Hindi script"),
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=COLORS["en"], markersize=10, label="English script"),
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=COLORS["other"], markersize=10, label="Other"),
    ]
    figure.legend(handles=handles, loc="lower center", ncol=3, frameon=False)
    figure.suptitle("Observed reasoning language by condition (model continuation only)", y=0.98)
    figure.tight_layout(rect=[0, 0.12, 1, 0.95])
    return _save(figure, dest / "mmlu_language_pies")


def paired_differences_heatmap(rows: list[dict[str, Any]], summary: dict[str, Any], dest: Path) -> Path:
    labels = [row["condition_id"] for row in rows]
    n = len(labels)
    matrix = np.zeros((n, n))
    p_values: dict[tuple[int, int], float] = {}
    for diff in summary["paired_differences"]:
        i = labels.index(diff["condition_a"])
        j = labels.index(diff["condition_b"])
        matrix[i, j] = diff["accuracy_difference_b_minus_a"] * 100
        matrix[j, i] = -diff["accuracy_difference_b_minus_a"] * 100
        p_values[(i, j)] = diff["mcnemar_p_value"]
        p_values[(j, i)] = diff["mcnemar_p_value"]
    span = max(5.0, np.abs(matrix).max() + 2)
    figure, axis = plt.subplots(figsize=(7.5, 6.2))
    heatmap = axis.imshow(matrix, cmap="RdBu_r", aspect="auto", vmin=-span, vmax=span)
    axis.set_xticks(range(n))
    axis.set_yticks(range(n))
    axis.set_xticklabels(labels, rotation=45, ha="right")
    axis.set_yticklabels(labels)
    for i in range(n):
        for j in range(n):
            p = p_values.get((i, j))
            label = f"{matrix[i, j]:+.1f}%" if j != i else ""
            if j != i and p is not None:
                label += f"\np={p:.2f}"
            axis.text(j, i, label, ha="center", va="center", fontsize=8, color="#111111")
    figure.colorbar(heatmap, ax=axis, label="B - A accuracy (pp)")
    axis.set_title("Paired MMLU accuracy differences (pp)\nMcNemar p-value in each cell; none significant (min p = 0.219)")
    figure.tight_layout()
    return _save(figure, dest / "mmlu_paired_differences_heatmap")


def per_problem_heatmap(traces: list[dict[str, Any]], summary: dict[str, Any], dest: Path) -> Path:
    condition_ids = [row["condition_id"] for row in summary["conditions"]]
    by_problem: dict[str, dict[str, str]] = {}
    for trace in traces:
        problem_id = trace["problem_id"]
        status_key = "correct" if trace["is_correct"] else ("unparseable" if not _has_explicit(trace) else "wrong")
        by_problem.setdefault(problem_id, {})[trace["condition_id"]] = status_key
    problem_ids = sorted(by_problem)
    status_map = {"correct": 1.0, "wrong": 0.0, "unparseable": 0.5}
    matrix = np.array(
        [[status_map[by_problem[pid][cond]] for cond in condition_ids] for pid in problem_ids]
    )
    figure, axis = plt.subplots(figsize=(7.5, max(4.5, 0.22 * len(problem_ids) + 2)))
    axis.imshow(matrix, cmap="RdYlGn", aspect="auto", vmin=0, vmax=1)
    axis.set_xticks(range(len(condition_ids)))
    axis.set_xticklabels(condition_ids, rotation=45, ha="right", fontsize=9)
    axis.set_yticks(range(len(problem_ids)))
    axis.set_yticklabels(problem_ids, fontsize=7)
    for i in range(len(problem_ids)):
        for j in range(len(condition_ids)):
            axis.text(j, i, "", ha="center", va="center", fontsize=4)
    handles = [
        plt.Line2D([0], [0], marker="s", color="w", markerfacecolor="#2E8B57", markersize=11, label="Correct"),
        plt.Line2D([0], [0], marker="s", color="w", markerfacecolor="#C0392B", markersize=11, label="Wrong"),
        plt.Line2D([0], [0], marker="s", color="w", markerfacecolor="#E6B800", markersize=11, label="Unparseable"),
    ]
    axis.legend(handles=handles, loc="lower right", frameon=True, fontsize=8)
    axis.set_title("Per-problem outcome by condition (33 problems)\nGreen=correct, red=wrong, amber=unparseable")
    figure.tight_layout()
    return _save(figure, dest / "mmlu_per_problem_heatmap")


def _has_explicit(trace: dict[str, Any]) -> bool:
    return trace.get("scoring_status", "scored") in {"scored", "adjudicated"}


def main() -> int:
    traces, summary = load_data()
    rows = _summary_rows(summary)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    figures = [
        table_image(rows, OUTPUT_DIR),
        accuracy_bar(rows, OUTPUT_DIR),
        error_counts_bar(rows, OUTPUT_DIR),
        language_pies(rows, OUTPUT_DIR),
        paired_differences_heatmap(rows, summary, OUTPUT_DIR),
        per_problem_heatmap(traces, summary, OUTPUT_DIR),
    ]
    for figure in figures:
        print(f"wrote {figure}")
    print(f"done: {len(figures)} figures in {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())