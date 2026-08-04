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

# Chinese-language signals for titles and uploaders. Substring matching is
# case-insensitive by nature for CJK; keep terms specific enough to avoid
# false positives (e.g. use "精华剪辑" instead of bare "剪辑" so "无剪辑"
# still counts as a positive signal).
_POSITIVE_SIGNALS_CN = (
    "官方",
    "新闻",
    "纪录片",
    "发布会",
    "直播",
    "完整版",
    "完整记录",
    "实录",
    "原始素材",
    "现场记录",
    "全程记录",
    "无剪辑",
    "央视",
    "新华社",
    "人民日报",
    "cgtn",
    "我们的太空",
    "中国航天",
)

_NEGATIVE_SIGNALS_CN = (
    "解说",
    "盘点",
    "混剪",
    "合集",
    "二创",
    "解读",
    "吐槽",
    "评测",
    "回顾",
    "翻录",
    "转载",
    "水印",
    "短视频",
    "精华剪辑",
    "精彩剪辑",
    "反应视频",
)

_OFFICIAL_CHANNEL_SIGNALS_CN = (
    "官方",
    "央视",
    "新华社",
    "人民日报",
    "cgtn",
    "新闻",
    "中国航天",
    "航天科技",
    "我们的太空",
    "人民政府",
    "博物馆",
    "档案馆",
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

    positive_hit = any(signal in combined for signal in _POSITIVE_SIGNALS)
    positive_cn_hit = any(signal in combined for signal in _POSITIVE_SIGNALS_CN)
    if positive_hit or positive_cn_hit:
        score = min(MAX_SCORE, score + 0.25)
        if positive_hit:
            reasons.append("positive:official-or-archival-signals")
        else:
            reasons.append("positive:cn-official-or-archival-signals")
    channel_hit = any(signal in uploader_lower for signal in _OFFICIAL_CHANNEL_SIGNALS)
    channel_cn_hit = any(signal in uploader_lower for signal in _OFFICIAL_CHANNEL_SIGNALS_CN)
    if channel_hit or channel_cn_hit:
        score = min(MAX_SCORE, score + 0.15)
        if channel_hit:
            reasons.append("positive:official-channel")
        else:
            reasons.append("positive:cn-official-channel")
    if is_live:
        score = min(MAX_SCORE, score + 0.05)
        reasons.append("positive:live-recording")

    negative_hit = any(signal in combined for signal in _NEGATIVE_SIGNALS)
    negative_cn_hit = any(signal in combined for signal in _NEGATIVE_SIGNALS_CN)
    if negative_hit or negative_cn_hit:
        score = max(0.0, score - 0.3)
        if negative_hit:
            reasons.append("negative:commentary-or-edit-signals")
        else:
            reasons.append("negative:cn-commentary-or-edit-signals")
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
        "positive:cn-official-or-archival-signals": (
            "Title or uploader contains Chinese official/archival/raw-footage signals"
        ),
        "positive:official-channel": "Uploader looks like an official channel or institution",
        "positive:cn-official-channel": (
            "Uploader looks like a Chinese official channel or institution"
        ),
        "positive:live-recording": "Candidate is a live recording",
        "negative:commentary-or-edit-signals": (
            "Title or uploader contains commentary/compilation/edit signals"
        ),
        "negative:cn-commentary-or-edit-signals": (
            "Title or uploader contains Chinese commentary/compilation/edit signals"
        ),
        "negative:short-form-duration": "Duration suggests a short-form clip",
        "negative:duplicate-candidate": "Same platform media ID already recorded",
    }
    return [mapping.get(reason, reason) for reason in reasons]
