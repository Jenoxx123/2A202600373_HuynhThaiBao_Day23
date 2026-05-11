"""Node functions for the LangGraph workflow."""

from __future__ import annotations

import os
import re

from .state import AgentState, ApprovalDecision, Route, make_event

RISKY_KEYWORDS = {"refund", "delete", "send", "cancel", "remove", "revoke"}
TOOL_KEYWORDS = {"status", "order", "lookup", "check", "track", "find", "search"}
ERROR_KEYWORDS = {"timeout", "error", "crash", "unavailable"}
MISSING_PRONOUNS = {"it", "this", "that"}
TOKEN_PATTERN = re.compile(r"[a-z0-9']+")


def _tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.lower())


def _has_any(tokens: list[str], keywords: set[str]) -> bool:
    return bool(set(tokens) & keywords)


def _has_error_signal(tokens: list[str]) -> bool:
    return any(token in ERROR_KEYWORDS or token.startswith("fail") for token in tokens)


def intake_node(state: AgentState) -> dict:
    """Normalize the incoming query before routing."""
    query = " ".join(state.get("query", "").strip().split())
    return {
        "query": query,
        "messages": [f"intake:{query[:60]}"],
        "events": [make_event("intake", "completed", "query normalized", length=len(query))],
    }


def classify_node(state: AgentState) -> dict:
    """Classify the query using keyword rules with fixed priority."""
    query = state.get("query", "")
    tokens = _tokenize(query)
    route = Route.SIMPLE
    risk_level = "low"

    if _has_any(tokens, RISKY_KEYWORDS):
        route = Route.RISKY
        risk_level = "high"
    elif _has_any(tokens, TOOL_KEYWORDS):
        route = Route.TOOL
        risk_level = "medium"
    elif len(tokens) < 5 and _has_any(tokens, MISSING_PRONOUNS):
        route = Route.MISSING_INFO
    elif _has_error_signal(tokens):
        route = Route.ERROR
        risk_level = "medium"

    return {
        "route": route.value,
        "risk_level": risk_level,
        "events": [make_event("classify", "completed", f"route={route.value}")],
    }


def ask_clarification_node(state: AgentState) -> dict:
    """Ask for missing information instead of hallucinating."""
    query = state.get("query", "")
    tokens = _tokenize(query)
    if _has_any(tokens, TOOL_KEYWORDS):
        question = "Please share the order ID or ticket number so I can continue."
    else:
        question = "Can you share a bit more detail about the issue and what failed?"
    return {
        "pending_question": question,
        "final_answer": question,
        "events": [make_event("clarify", "completed", "missing information requested")],
    }


def tool_node(state: AgentState) -> dict:
    """Execute a deterministic mock tool call."""
    attempt = int(state.get("attempt", 0))
    scenario_id = state.get("scenario_id", "unknown")
    route = state.get("route")
    query = state.get("query", "").lower()

    if route == Route.ERROR.value and attempt < 2:
        result = f"ERROR: transient failure attempt={attempt} scenario={scenario_id}"
    elif "order" in query:
        result = f"mock-tool-result: order status resolved for scenario={scenario_id}"
    else:
        result = f"mock-tool-result for scenario={scenario_id}"

    return {
        "tool_results": [result],
        "events": [make_event("tool", "completed", f"tool executed attempt={attempt}")],
    }


def risky_action_node(state: AgentState) -> dict:
    """Prepare a risky action proposal for approval."""
    query = state.get("query", "")
    return {
        "proposed_action": f"Proposed risky action from query: {query[:80]}",
        "events": [make_event("risky_action", "pending_approval", "approval required")],
    }


def approval_node(state: AgentState) -> dict:
    """Human approval step with optional LangGraph interrupt for demos."""
    if os.getenv("LANGGRAPH_INTERRUPT", "").lower() == "true":
        from langgraph.types import interrupt

        value = interrupt(
            {
                "proposed_action": state.get("proposed_action"),
                "risk_level": state.get("risk_level"),
            }
        )
        if isinstance(value, dict):
            decision = ApprovalDecision(**value)
        else:
            decision = ApprovalDecision(approved=bool(value))
    else:
        decision = ApprovalDecision(approved=True, comment="mock approval for lab")
    return {
        "approval": decision.model_dump(),
        "events": [make_event("approval", "completed", f"approved={decision.approved}")],
    }


def retry_or_fallback_node(state: AgentState) -> dict:
    """Increment retry counters and log bounded retry metadata."""
    attempt = int(state.get("attempt", 0)) + 1
    backoff_seconds = min(2 ** max(attempt - 1, 0), 8)
    return {
        "attempt": attempt,
        "errors": [f"transient failure attempt={attempt}"],
        "events": [
            make_event(
                "retry",
                "completed",
                "retry attempt recorded",
                attempt=attempt,
                backoff_seconds=backoff_seconds,
            )
        ],
    }


def answer_node(state: AgentState) -> dict:
    """Produce a final response grounded in tool output and approval state."""
    tool_results = state.get("tool_results", [])
    approval = state.get("approval") or {}
    route = state.get("route")

    if tool_results:
        answer = f"I found: {tool_results[-1]}"
    else:
        answer = "I can help with this request."

    if route == Route.RISKY.value and approval.get("approved"):
        answer = f"{answer} Approval has been recorded and the action is authorized."

    return {
        "final_answer": answer,
        "events": [make_event("answer", "completed", "answer generated")],
    }


def evaluate_node(state: AgentState) -> dict:
    """Evaluate tool results to decide whether the graph should retry."""
    tool_results = state.get("tool_results", []) or []
    latest = str(tool_results[-1]) if tool_results else ""
    if "ERROR" in latest.upper():
        return {
            "evaluation_result": "needs_retry",
            "events": [
                make_event("evaluate", "completed", "tool result indicates failure, retry needed")
            ],
        }
    return {
        "evaluation_result": "success",
        "events": [make_event("evaluate", "completed", "tool result satisfactory")],
    }


def dead_letter_node(state: AgentState) -> dict:
    """Record an unresolvable request for manual handling."""
    scenario_id = state.get("scenario_id", "unknown")
    attempt = int(state.get("attempt", 0))
    return {
        "final_answer": (
            "Request could not be completed after maximum retry attempts. "
            f"Logged for manual review (scenario={scenario_id}, attempts={attempt})."
        ),
        "events": [
            make_event("dead_letter", "completed", f"max retries exceeded, attempt={attempt}")
        ],
    }


def finalize_node(state: AgentState) -> dict:
    """Finalize the run and emit a final audit event."""
    return {"events": [make_event("finalize", "completed", "workflow finished")]}
