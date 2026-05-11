# Day 08 Lab Report

## 1. Team / student

- Name: Huynh Thai Bao
- Repo/commit: local workspace, Day 23 lab
- Date: 2026-05-11

## 2. Architecture

This lab implements a LangGraph support-ticket workflow with typed state, conditional routing,
bounded retries, human approval for risky actions, persistence, and metrics.

Graph flow:

- `START -> intake -> classify`
- `simple -> answer -> finalize -> END`
- `tool -> tool -> evaluate -> answer -> finalize -> END`
- `missing_info -> clarify -> finalize -> END`
- `risky -> risky_action -> approval -> tool -> evaluate -> answer -> finalize -> END`
- `error -> retry -> tool -> evaluate -> retry/answer/dead_letter -> finalize -> END`

Classifier priority:

- risky keywords first: `refund`, `delete`, `send`, `cancel`, `remove`, `revoke`
- then tool keywords: `status`, `order`, `lookup`, `check`, `track`, `find`, `search`
- then short/vague missing-info queries with pronouns such as `it`, `this`, `that`
- then error keywords: `timeout`, `fail`, `failure`, `error`, `crash`, `unavailable`
- otherwise default to `simple`

## 3. State schema

The state is lean and serializable. Audit/history fields are append-only; current decisions and
outputs are overwritten.

| Field | Reducer | Why |
|---|---|---|
| `messages` | append | Keeps a lightweight message trace. |
| `tool_results` | append | Preserves tool outputs for evaluation and debugging. |
| `errors` | append | Records retry and failure history. |
| `events` | append | Drives metrics and node-visit evidence. |
| `route` | overwrite | Stores the current route decision. |
| `risk_level` | overwrite | Stores the latest risk classification. |
| `attempt` | overwrite | Tracks the current retry attempt. |
| `final_answer` | overwrite | Stores the final response. |
| `pending_question` | overwrite | Stores clarification output. |
| `approval` | overwrite | Stores the latest approval decision. |
| `evaluation_result` | overwrite | Gates retry vs answer after tool evaluation. |

## 4. Scenario results

| Scenario | Expected route | Actual route | Success | Retries | Interrupts |
|---|---|---|---:|---:|---:|
| S01_simple | simple | simple | true | 0 | 0 |
| S02_tool | tool | tool | true | 0 | 0 |
| S03_missing | missing_info | missing_info | true | 0 | 0 |
| S04_risky | risky | risky | true | 0 | 9 |
| S05_error | error | error | true | 25 | 0 |
| S06_delete | risky | risky | true | 0 | 9 |
| S07_dead_letter | error | error | true | 9 | 0 |

Summary:

- Total scenarios: 7
- Success rate: 100.00%
- Average nodes visited: 58.86
- Total retries: 34
- Total interrupts: 18
- Metrics validation: passed

Note: retry, interrupt, and node counts may be higher than a clean single run because
PostgreSQL persistence reuses deterministic `thread_id` values across repeated runs.
This demonstrates persisted state history. For a clean benchmark, reset checkpoint tables or
use fresh thread IDs.

## 5. Failure analysis

1. Retry or tool failure:
The `error` route starts at `retry`, then calls `tool`. For transient failures, `tool` emits an
`ERROR` result. `evaluate` converts that into `evaluation_result=needs_retry`, and routing sends the
graph back through `retry`. The loop is bounded by `attempt >= max_attempts`; exhausted
requests go to `dead_letter` and still terminate through `finalize`.

2. Risky action without approval:
Risky queries route to `risky_action` before tool execution. The graph then requires `approval`.
If approval is false, `route_after_approval` sends the request to `clarify` instead of executing
the action.

3. Keyword conflicts:
Risky keywords have priority over tool keywords. A query like "remove account and check
order status" routes to `risky`, not `tool`, because destructive/external actions are higher risk.

## 6. Persistence / recovery evidence

- Checkpointer used: `postgres`
- Config file: `configs/lab.yaml`
- Database URL: `postgresql://postgres:***@localhost:5432/langgraph_lab`
- Thread ID strategy: `thread-<scenario_id>`
- Expected PostgreSQL tables: `checkpoint_migrations`, `checkpoints`, `checkpoint_writes`,
  `checkpoint_blobs`
- Evidence: repeated runs accumulate checkpoint state and metrics for the same deterministic
  thread IDs.

## 7. Extension work

Completed extension: PostgreSQL persistence.

- `build_checkpointer()` supports `memory`, `none`, `sqlite`, and `postgres`.
- PostgreSQL uses `langgraph-checkpoint-postgres`.
- Compatibility fix keeps the context manager returned by `PostgresSaver.from_conn_string(...)`
  alive.
- SQLite support uses `sqlite3.connect(...)`, WAL mode, and `SqliteSaver(conn=...)`.

Quality checks completed:

- `python -m pytest`: passed
- `python -m langgraph_agent_lab.cli validate-metrics --metrics outputs/metrics.json`: passed
- `python -m ruff check src tests`: passed
- `python -m mypy src`: passed

## 8. Improvement plan

If I had one more day, I would productionize three areas first:

1. Add a clean-run option that generates fresh thread IDs or clears checkpoint tables before
   metrics.
2. Add a crash-resume demo that intentionally stops after a checkpoint and resumes the same thread.
3. Replace keyword routing with structured classification and add richer latency/error metrics
   per node.
