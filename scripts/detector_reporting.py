"""Aggregate detector results and render the experiment report."""

from __future__ import annotations

import statistics
from pathlib import Path


def aggregate(runs: list[dict[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    metric_names = (
        "precision",
        "recall",
        "f1",
        "false_alerts_per_hour",
        "detection_delay_p50_seconds",
        "detection_delay_p95_seconds",
        "recovery_p50_seconds",
        "recovery_p95_seconds",
        "small_traffic_false_positives",
        "small_traffic_false_positive_rate",
        "missed_faults",
    )
    for strategy in ("fixed", "rule", "ewma_mad"):
        values = [run["strategies"][strategy] for run in runs]  # type: ignore[index]
        strategy_result = {}
        for metric in metric_names:
            numbers = [float(value[metric]) for value in values if value[metric] is not None]
            strategy_result[metric] = (
                {
                    "mean": round(statistics.mean(numbers), 6),
                    "median": round(statistics.median(numbers), 6),
                    "min": min(numbers),
                    "max": max(numbers),
                    "sample_count": len(numbers),
                }
                if numbers
                else {"mean": None, "median": None, "min": None, "max": None, "sample_count": 0}
            )
        result[strategy] = strategy_result
    return result


def write_markdown(summary: dict[str, object], path: Path) -> None:
    lines = [
        "# Detector comparison",
        "",
        "Synthetic, fixed-seed local evidence. Missing or weak results are retained.",
        "",
        f"Runs: **{summary['run_count']}**; three-run gate: **{summary['acceptance_run_count_met']}**; "
        f"manifest evidence complete: **{summary['manifest_evidence_complete']}**.",
        "",
        "| Strategy | Precision mean/median/range | Recall mean/median/range | F1 mean/median/range | False alerts/hour mean | Detection P95 mean (s) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    aggregate_rows = summary["aggregate"]  # type: ignore[index]
    for strategy in ("fixed", "rule", "ewma_mad"):
        item = aggregate_rows[strategy]

        def spread(metric: str) -> str:
            values = item[metric]
            return f"{values['mean']:.6f}/{values['median']:.6f}/[{values['min']:.6f}, {values['max']:.6f}]"

        delay = item["detection_delay_p95_seconds"]["mean"]
        lines.append(
            f"| `{strategy}` | {spread('precision')} | {spread('recall')} | {spread('f1')} | "
            f"{item['false_alerts_per_hour']['mean']:.6f} | {delay if delay is not None else 'N/A'} |"
        )
    lines.extend(
        [
            "",
            "## Per-run results",
            "",
            "| Run | Strategy | Precision | Recall | F1 | Missed faults |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for run in summary["runs"]:  # type: ignore[index]
        for strategy in ("fixed", "rule", "ewma_mad"):
            item = run["strategies"][strategy]
            lines.append(
                f"| `{run['run_id']}` | `{strategy}` | {item['precision']:.6f} | "
                f"{item['recall']:.6f} | {item['f1']:.6f} | {item['missed_faults']} |"
            )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The fixed threshold and EWMA/MAD baseline tied on these deliberately strong synthetic faults; "
            "this does not show that either generalizes to changing production traffic.",
            "The combined rule was retained despite weak recall: requiring latency and error evidence together "
            "missed latency-only and error-only windows.",
            "Each raw node-metric file and manifest is SHA-256 identified in `summary.json`; per-window labels, "
            "predictions, metrics, and reason codes are stored in the three `*-predictions.jsonl` files.",
            "",
            "Detection uses completed-window timestamps. EWMA/MAD sees only past windows; no future rows are included.",
            "This report does not establish causal QoE improvement or production-scale performance.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
