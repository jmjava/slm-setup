"""Layered scoring for local-coding-slm tool output.

This package does not talk to Ollama. It scores a candidate string the same
way whether the string came from a live MCP call or a committed fixture.
"""

from local_coding_slm.eval.extract import ExtractedFile, TransportError, extract_files
from local_coding_slm.eval.score import (
    BehaviorCheck,
    EvalCase,
    EvalResult,
    LayerResult,
    score_candidate,
)

__all__ = [
    "BehaviorCheck",
    "EvalCase",
    "EvalResult",
    "ExtractedFile",
    "LayerResult",
    "TransportError",
    "extract_files",
    "score_candidate",
]
