"""Configurable media quality profiles (Issue #43).

Pre-download evaluation uses the compact format summary captured by the
candidate preflight; post-download evaluation uses ffprobe fields. The
default profile suits normal landscape editing.
"""

from __future__ import annotations

from typing import Any

DEFAULT_QUALITY_PROFILE: dict[str, Any] = {
    "preferred_height": 1080,
    "minimum_height": 720,
    "minimum_fps": 24,
    "minimum_video_bitrate": None,
    "prefer_landscape": True,
    "allow_vertical": False,
    "allow_below_minimum": False,
}

FORMAT_OK = "OK"
FORMAT_NO_QUALIFYING = "NO_QUALIFYING_FORMAT"
FORMAT_INFO_UNAVAILABLE = "FORMAT_INFO_UNAVAILABLE"

_FLOAT_KEYS = {"minimum_height", "minimum_fps", "minimum_video_bitrate", "preferred_height"}
_BOOL_KEYS = {"prefer_landscape", "allow_vertical", "allow_below_minimum"}


def default_quality_profile() -> dict[str, Any]:
    return dict(DEFAULT_QUALITY_PROFILE)


def validate_quality_profile(profile: dict[str, Any] | None) -> dict[str, Any]:
    """Validate and normalize a profile; malformed profiles are rejected."""
    if profile is None:
        return default_quality_profile()
    result = default_quality_profile()
    for key in _FLOAT_KEYS:
        if key not in profile:
            continue
        value = profile[key]
        if value is None:
            result[key] = None
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"quality profile '{key}' must be a number or null")
        if key == "minimum_height" and value < 0:
            raise ValueError("quality profile 'minimum_height' must be >= 0")
        if key == "minimum_fps" and value < 0:
            raise ValueError("quality profile 'minimum_fps' must be >= 0")
        if key == "minimum_video_bitrate" and value < 0:
            raise ValueError("quality profile 'minimum_video_bitrate' must be >= 0")
        if key == "preferred_height" and value < 0:
            raise ValueError("quality profile 'preferred_height' must be >= 0")
        result[key] = value
    for key in _BOOL_KEYS:
        if key in profile:
            if not isinstance(profile[key], bool):
                raise ValueError(f"quality profile '{key}' must be a boolean")
            result[key] = profile[key]
    minimum = result["minimum_height"]
    preferred = result["preferred_height"]
    if minimum and preferred and preferred < minimum:
        raise ValueError("quality profile 'preferred_height' must be >= 'minimum_height'")
    return result


def evaluate_format_summary(
    summary: dict[str, Any] | None, profile: dict[str, Any]
) -> tuple[str, list[str]]:
    """Evaluate the compact format summary against the profile.

    Returns (FORMAT_OK | FORMAT_NO_QUALIFYING | FORMAT_INFO_UNAVAILABLE, reasons).
    """
    reasons: list[str] = []
    if not summary or not isinstance(summary.get("count"), int) or summary["count"] == 0:
        return FORMAT_INFO_UNAVAILABLE, ["no format information available"]

    minimum_height = profile.get("minimum_height")
    max_height = summary.get("max_height")
    if minimum_height and not isinstance(max_height, int):
        return FORMAT_INFO_UNAVAILABLE, ["format heights unavailable"]
    if minimum_height and isinstance(max_height, int) and max_height < minimum_height:
        reasons.append(f"max height {max_height} < minimum {minimum_height}")

    minimum_fps = profile.get("minimum_fps")
    max_fps = summary.get("max_fps")
    if minimum_fps and not isinstance(max_fps, int):
        return FORMAT_INFO_UNAVAILABLE, ["format fps unavailable"]
    if minimum_fps and isinstance(max_fps, int) and max_fps < minimum_fps:
        reasons.append(f"max fps {max_fps} < minimum {minimum_fps}")

    minimum_bitrate = profile.get("minimum_video_bitrate")
    max_bitrate = summary.get("max_bitrate")
    if minimum_bitrate and not isinstance(max_bitrate, (int, float)):
        return FORMAT_INFO_UNAVAILABLE, ["format bitrate unavailable"]
    if minimum_bitrate and isinstance(max_bitrate, (int, float)) and max_bitrate < minimum_bitrate:
        reasons.append(f"max bitrate {max_bitrate} < minimum {minimum_bitrate}")

    if reasons:
        return FORMAT_NO_QUALIFYING, reasons
    return FORMAT_OK, ["qualifying format available"]


def build_format_selector(profile: dict[str, Any]) -> str:
    """Build a controlled yt-dlp format expression from the profile.

    Keeps the audio fallback. Below-minimum fallback is only used when
    ``allow_below_minimum`` is explicitly enabled in the profile.
    """
    filters = []
    minimum_height = profile.get("minimum_height")
    if minimum_height:
        filters.append(f"height>={int(minimum_height)}")
    minimum_fps = profile.get("minimum_fps")
    if minimum_fps:
        filters.append(f"fps>={int(minimum_fps)}")
    minimum_bitrate = profile.get("minimum_video_bitrate")
    if minimum_bitrate:
        filters.append(f"vbr>={int(minimum_bitrate)}")
    if not filters:
        return "bv*+ba/b"
    suffix = "".join(f"[{item}]" for item in filters)
    if profile.get("allow_below_minimum"):
        return f"bv*{suffix}/b"
    return f"bv*{suffix}+ba/b"


def evaluate_media_fields(
    media: dict[str, Any] | None, profile: dict[str, Any]
) -> tuple[str, list[str]]:
    """Evaluate post-download ffprobe fields; returns (quality_status, reasons)."""
    if not media:
        return "UNKNOWN", ["media inspection unavailable"]
    reasons: list[str] = []
    width = media.get("width")
    height = media.get("height")
    minimum_height = profile.get("minimum_height")
    if minimum_height and isinstance(height, int) and height < minimum_height:
        reasons.append(f"height {height} < minimum {minimum_height}")
    if not reasons:
        minimum_fps = profile.get("minimum_fps")
        fps = media.get("fps")
        if minimum_fps and isinstance(fps, float) and fps < minimum_fps:
            reasons.append(f"fps {fps} < minimum {minimum_fps}")
    if not reasons:
        minimum_bitrate = profile.get("minimum_video_bitrate")
        video_bitrate = media.get("video_bitrate")
        if (
            minimum_bitrate
            and isinstance(video_bitrate, (int, float))
            and video_bitrate < minimum_bitrate
        ):
            reasons.append(f"video bitrate {video_bitrate} < minimum {minimum_bitrate}")
    if not reasons:
        allow_vertical = profile.get("allow_vertical")
        if width and height and height > width and not allow_vertical:
            reasons.append("vertical orientation not allowed")
    if not reasons:
        return "PASS", ["meets quality profile"]
    if profile.get("allow_below_minimum"):
        return "WARN", reasons
    return "REJECT", reasons
