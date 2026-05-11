"""Report generation helper."""

from __future__ import annotations

from pathlib import Path

from .metrics import MetricsReport


def render_report_stub(metrics: MetricsReport) -> str:
    """Return a structured report draft that can be completed for submission."""
    rows = "\n".join(
        "| {id} | {expected} | {actual} | {success} | {retry} | {interrupt} |".format(
            id=item.scenario_id,
            expected=item.expected_route,
            actual=item.actual_route or "n/a",
            success=str(item.success).lower(),
            retry=item.retry_count,
            interrupt=item.interrupt_count,
        )
        for item in metrics.scenario_metrics
    )

    return f"""# Day 08 Lab Report

## 1. Team / student

- Name:
- Repo/commit:
- Date:

## 2. Architecture

Describe your graph nodes, routing, and retry/approval flow.

## 3. State schema

Describe append-only vs overwrite fields and why.

## 4. Scenario results

| Scenario | Expected route | Actual route | Success | Retries | Interrupts |
|---|---|---|---:|---:|---:|
{rows}

Summary:

- Total scenarios: {metrics.total_scenarios}
- Success rate: {metrics.success_rate:.2%}
- Average nodes visited: {metrics.avg_nodes_visited:.2f}
- Total retries: {metrics.total_retries}
- Total interrupts: {metrics.total_interrupts}

## 5. Failure analysis

1. Retry or tool failure:
2. Risky action without approval:

## 6. Persistence / recovery evidence

- Checkpointer used:
- Thread id strategy:
- Evidence:

## 7. Extension work

Describe any extension completed (SQLite/Postgres, replay, fan-out, diagram).

## 8. Improvement plan

If you had one more day, what would you productionize first?
"""


def write_report(metrics: MetricsReport, output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report_stub(metrics), encoding="utf-8")
