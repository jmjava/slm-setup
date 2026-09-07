"""Spec §8 routing as an explicit decision, not a learned classifier.

The premium agent still chooses the signals. This module is the contract
those signals must satisfy: mechanical work may be delegated; incident,
architectural, and live-tool work stays on the premium model. Delegated
work always requires a later premium review before apply.
"""

from __future__ import annotations

from dataclasses import dataclass


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


def route(signals: RouteSignals) -> RouteDecision:
    """Return keep vs delegate. Do-not-delegate flags win over mechanical ones."""
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
