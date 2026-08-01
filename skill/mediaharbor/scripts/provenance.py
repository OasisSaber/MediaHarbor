"""Deterministic, explainable provenance scoring for candidates.

Heuristics only; no ML. Every score component appends a human-readable reason
so the Agent and the operator can understand the decision. Technical quality
(resolution/FPS/bitrate) is owned by Issue #43 and is deliberately not scored
here.
"""

from __future__ import annotations

MIN_PROVENANCE_THRESHOLD = 0.5

_POSITIVE_SIGNALS = (
    "official",
    "institution",
    "archive",
    "broadcast",
    "news",
    "documentary",
    "press conference",
    "full speech",
    "full address",
    "unedited",
    "raw footage",
    "b-roll",
    "original footage",
    "complete recording",
    "clean feed",
)

_NEGATIVE_SIGNALS = (
    "commentary",
    "explainer",
    "reaction",
    "recap",
    "compilation",
    "fan edit",
    "remix",
    "highlight",
    "reupload",
    "shorts",
    "subtitle",
    "subtitles",
    "watermark",
    "heavy edit",
    "heavily edited",
)

_OFFICIAL_CHANNEL_SIGNALS = (
    "official",
    "institution",
    "university",
    "ministry",
    "government",
    "archives",
    "museum",
    "news",
    "newsroom",
)

MAX_SCORE = 1.0


def score_candidate(
    title: str | None,
    uploader: str | None,
    duration: float | None,
    is_live: bool | None,
    duplicate: bool,
) -> tuple[float, list[str]]:
    """Return (score, reasons). Score in [0, 1]; 0.5 is the default threshold."""
    title_lower = (title or "").lower()
    uploader_lower = (uploader or "").lower()
    combined = f"{title_lower} {uploader_lower}"
    reasons: list[str] = []
    score = 0.5

    if any(signal in combined for signal in _POSITIVE_SIGNALS):
        score = min(MAX_SCORE, score + 0.25)
        reasons.append("positive:official-or-archival-signals")
    if any(signal in uploader_lower for signal in _OFFICIAL_CHANNEL_SIGNALS):
        score = min(MAX_SCORE, score + 0.15)
        reasons.append("positive:official-channel")
    if is_live:
        score = min(MAX_SCORE, score + 0.05)
        reasons.append("positive:live-recording")

    if any(signal in combined for signal in _NEGATIVE_SIGNALS):
        score = max(0.0, score - 0.3)
        reasons.append("negative:commentary-or-edit-signals")
    if duration is not None and duration < 60:
        score = max(0.0, score - 0.2)
        reasons.append("negative:short-form-duration")
    if duplicate:
        score = max(0.0, score - 0.25)
        reasons.append("negative:duplicate-candidate")

    return score, reasons


def reasons_to_messages(reasons: list[str]) -> list[str]:
    mapping = {
        "positive:official-or-archival-signals": (
            "Title or uploader contains official/archival/raw-footage signals"
        ),
        "positive:official-channel": "Uploader looks like an official channel or institution",
        "positive:live-recording": "Candidate is a live recording",
        "negative:commentary-or-edit-signals": (
            "Title or uploader contains commentary/compilation/edit signals"
        ),
        "negative:short-form-duration": "Duration suggests a short-form clip",
        "negative:duplicate-candidate": "Same platform media ID already recorded",
    }
    return [mapping.get(reason, reason) for reason in reasons]
