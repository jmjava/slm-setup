"""Spec §8 routing as an explicit decision, not a learned classifier.

The premium agent still chooses the signals. This module is the contract
those signals must satisfy: mechanical work may be delegated; incident,
architectural, and live-tool work stays on the premium model. Delegated
work always requires a later premium review before apply. Secret files
never go to local_* even when the task looks mechanical.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from local_coding_slm.payload import inspect_payload


@dataclass(frozen=True)
class RouteSignals:
    """What a premium orchestrator claims about a task before calling local_*."""

    shape_obvious: bool = False
    context_fits: bool = False
    wrong_answer_cheap: bool = False
    architectural: bool = False
    incident_debug: bool = False
    needs_live_tools: bool = False
    security_sensitive: bool = False


@dataclass(frozen=True)
class RouteDecision:
    action: str  # "delegate" | "keep"
    reason: str
    requires_premium_review: bool


def mechanical_signals(**overrides: bool) -> RouteSignals:
    """Well-specified rename / tests / extract. Overrides layer extra flags."""
    values = {
        "shape_obvious": True,
        "context_fits": True,
        "wrong_answer_cheap": True,
    }
    values.update(overrides)
    return RouteSignals(**values)


def payload_block_reason(files: Sequence[dict[str, str]] | None) -> str | None:
    """Refuse secrets, credential files, and oversized snippets."""
    return inspect_payload(files)


def route(
    signals: RouteSignals,
    files: Sequence[dict[str, str]] | None = None,
) -> RouteDecision:
    """Return keep vs delegate. Do-not-delegate flags and secret files win."""
    blocked = payload_block_reason(files)
    if blocked:
        return RouteDecision("keep", blocked, False)
    if signals.incident_debug:
        return RouteDecision("keep", "incident_debug", False)
    if signals.architectural:
        return RouteDecision("keep", "architectural", False)
    if signals.needs_live_tools:
        return RouteDecision("keep", "needs_live_tools", False)
    if not (
        signals.shape_obvious
        and signals.context_fits
        and signals.wrong_answer_cheap
    ):
        return RouteDecision("keep", "not_mechanical", False)
    reason = (
        "mechanical_security_sensitive"
        if signals.security_sensitive
        else "mechanical"
    )
    return RouteDecision("delegate", reason, True)
