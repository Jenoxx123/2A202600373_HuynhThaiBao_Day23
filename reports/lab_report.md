# Day 08 Lab Report

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
| S01_simple | simple | simple | true | 0 | 0 |
| S02_tool | tool | tool | true | 0 | 0 |
| S03_missing | missing_info | missing_info | true | 0 | 0 |
| S04_risky | risky | risky | true | 0 | 7 |
| S05_error | error | error | true | 19 | 0 |
| S06_delete | risky | risky | true | 0 | 7 |
| S07_dead_letter | error | error | true | 7 | 0 |

Summary:

- Total scenarios: 7
- Success rate: 100.00%
- Average nodes visited: 45.71
- Total retries: 26
- Total interrupts: 14

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
