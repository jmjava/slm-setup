"""Premium-model apply gate. local_review is not this gate.

The MCP tool ``local_review`` is a cheap first-pass on the private SLM.
Apply still requires a verdict from the premium orchestrator
(accept / rewrite / reject). CI uses a scripted stand-in so the contract
is testable without calling Cursor, GPT, or Claude.

The handoff into review is a ``ReviewPacket``: local text, layer scores,
and optional local_review notes. The premium model is supposed to read
that packet, not only the raw tool string.
"""

from __future__ import annotations

from dataclasses import dataclass, field

PREMIUM_REVIEWER = "premium"
LOCAL_REVIEW_TOOL = "local_review"
DECISIONS = frozenset({"accept", "rewrite", "reject"})


@dataclass(frozen=True)
class ReviewPacket:
    """What the premium reviewer sees after local_* returns."""

    job_id: str
    local_text: str
    passed: bool
    layers: dict[str, str] = field(default_factory=dict)
    first_failure: str | None = None
    local_review_notes: str = ""
    case_id: str = ""


@dataclass(frozen=True)
class ReviewVerdict:
    decision: str
    reviewer: str = PREMIUM_REVIEWER
    text: str = ""
    notes: str = ""


def accept(*, notes: str = "") -> ReviewVerdict:
    return ReviewVerdict(decision="accept", notes=notes)


def rewrite(text: str, *, notes: str = "") -> ReviewVerdict:
    return ReviewVerdict(decision="rewrite", text=text, notes=notes)


def reject(*, notes: str = "") -> ReviewVerdict:
    return ReviewVerdict(decision="reject", notes=notes)


def is_premium_review(verdict: ReviewVerdict | None) -> bool:
    return (
        verdict is not None
        and verdict.reviewer == PREMIUM_REVIEWER
        and verdict.decision in DECISIONS
    )


class ScriptedReviewer:
    """Deterministic stand-in for the main LLM. Not a live API client."""

    def __init__(self, verdict: ReviewVerdict | None) -> None:
        self.verdict = verdict
        self.calls = 0
        self.last_packet: ReviewPacket | None = None

    def review(self, job_id: str, local_text: str, passed: bool) -> ReviewVerdict | None:
        del job_id, local_text, passed
        self.calls += 1
        return self.verdict

    def review_packet(self, packet: ReviewPacket) -> ReviewVerdict | None:
        self.last_packet = packet
        return self.review(packet.job_id, packet.local_text, packet.passed)
