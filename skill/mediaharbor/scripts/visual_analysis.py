"""Local, explainable, best-effort visual-contamination analysis (Issue #45).

Samples a small set of representative frames with local ffmpeg, then applies
deterministic region heuristics on downscaled raw RGB data: persistent
bottom-band text -> subtitle risk; stable corner regions -> watermark risk;
high overall text density -> text-heavy; inset panel structure -> PiP /
commentary risk. No OCR semantics, no cloud services, no full-video decode.

An optional registered OCR tool may be configured; when configured but
missing, analysis reports ``ANALYSIS_UNAVAILABLE`` instead of a false clean
result.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from _common import resolve_registered_tool
from process_runner import ProcessRunner

DEFAULT_VISUAL_CONFIG: dict[str, Any] = {
    "frame_count": 6,
    "max_analysis_duration": 600,
    "text_area_warning_threshold": 0.15,
    "text_area_reject_threshold": 0.35,
    "subtitle_persistence_threshold": 0.5,
    "watermark_persistence_threshold": 0.5,
    "analysis_failure_blocks": False,
    "retain_debug_frames": False,
    "ocr_tool": None,
}

SAMPLE_WIDTH = 160
SAMPLE_HEIGHT = 90

LABEL_CLEAN = "CLEAN"
LABEL_TEXT_HEAVY = "TEXT_HEAVY"
LABEL_SUBTITLES = "PERSISTENT_SUBTITLES"
LABEL_WATERMARK = "WATERMARK_LIKELY"
LABEL_PIP = "MULTI_PANEL_OR_PIP"
LABEL_COMMENTARY = "COMMENTARY_LAYOUT_LIKELY"
LABEL_UNAVAILABLE = "ANALYSIS_UNAVAILABLE"
LABEL_UNKNOWN = "UNKNOWN"


def validate_visual_config(config: dict[str, Any] | None) -> dict[str, Any]:
    if config is None:
        return dict(DEFAULT_VISUAL_CONFIG)
    result = dict(DEFAULT_VISUAL_CONFIG)
    for key in (
        "frame_count",
        "max_analysis_duration",
        "text_area_warning_threshold",
        "text_area_reject_threshold",
        "subtitle_persistence_threshold",
        "watermark_persistence_threshold",
    ):
        if key not in config:
            continue
        value = config[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"visual config '{key}' must be a number")
        if value < 0:
            raise ValueError(f"visual config '{key}' must be >= 0")
        result[key] = value
    for key in ("analysis_failure_blocks", "retain_debug_frames"):
        if key in config:
            if not isinstance(config[key], bool):
                raise ValueError(f"visual config '{key}' must be a boolean")
            result[key] = config[key]
    if "ocr_tool" in config:
        if config["ocr_tool"] is not None and not isinstance(config["ocr_tool"], str):
            raise ValueError("visual config 'ocr_tool' must be a string or null")
        result["ocr_tool"] = config["ocr_tool"]
    frame_count = result["frame_count"]
    if not (1 <= frame_count <= 30):
        raise ValueError("visual config 'frame_count' must be in 1..30")
    return result


def _resolve_ffmpeg() -> Path | None:
    try:
        result = resolve_registered_tool("ffmpeg")
        if result:
            return result
    except Exception:
        pass
    return None


def _media_duration(media_path: Path) -> float | None:
    from ffprobe_validator import parse_ffprobe_output, resolve_ffprobe, validate_media

    ffprobe = resolve_ffprobe()
    if ffprobe is None:
        return None
    result = validate_media(media_path)
    if result.status != "SUCCESS":
        return None
    info = parse_ffprobe_output(result.stdout)
    if not info:
        return None
    try:
        return float(info.get("format", {}).get("duration", 0))
    except (TypeError, ValueError):
        return None


def sample_frames(
    media_path: Path,
    work_dir: Path,
    config: dict[str, Any],
    runner: ProcessRunner | None = None,
) -> list[Path] | None:
    """Extract representative frames as raw RGB files; None on failure."""
    ffmpeg = _resolve_ffmpeg()
    if ffmpeg is None:
        return None
    work_dir.mkdir(parents=True, exist_ok=True)
    frame_count = int(config["frame_count"])
    duration = _media_duration(media_path)
    if duration is None or duration <= 0:
        duration = frame_count  # unknown: treat as one frame per sample
    if duration <= frame_count:
        times = [max(0.0, i) for i in range(frame_count)]
    else:
        times = [i * (duration / frame_count) for i in range(frame_count)]
    if runner is None:
        runner = ProcessRunner()
    frames: list[Path] = []
    for index, sample_time in enumerate(times):
        frame_path = work_dir / f"frame_{index:02d}.rgb"
        cmd = [
            str(ffmpeg),
            "-ss",
            f"{sample_time:.3f}",
            "-i",
            str(media_path),
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{SAMPLE_WIDTH}x{SAMPLE_HEIGHT}",
            "-y",
            str(frame_path),
        ]
        result = runner.run(cmd, backend="ffmpeg", check_drm=False)
        if result.status != "SUCCESS" or not frame_path.is_file():
            continue
        frames.append(frame_path)
        if config.get("retain_debug_frames"):
            thumb_path = work_dir / f"frame_{index:02d}.jpg"
            thumb_cmd = [
                str(ffmpeg),
                "-ss",
                f"{sample_time:.3f}",
                "-i",
                str(media_path),
                "-frames:v",
                "1",
                "-q:v",
                "2",
                "-y",
                str(thumb_path),
            ]
            runner.run(thumb_cmd, backend="ffmpeg", check_drm=False)
    return frames or None


def _edge_density(frame: bytes) -> float:
    """Mean normalized horizontal-gradient magnitude across the frame."""
    total = 0.0
    count = 0
    row_bytes = SAMPLE_WIDTH * 3
    for row in range(SAMPLE_HEIGHT):
        offset = row * row_bytes
        for col in range(1, SAMPLE_WIDTH):
            i = offset + col * 3
            prev = offset + (col - 1) * 3
            diff = (
                abs(frame[i] - frame[prev])
                + abs(frame[i + 1] - frame[prev + 1])
                + abs(frame[i + 2] - frame[prev + 2])
            ) / 3.0
            total += diff
            count += 1
    if count == 0:
        return 0.0
    return total / (count * 255.0)


def _region_density(frame: bytes, x0: int, y0: int, x1: int, y1: int) -> float:
    """Edge density within a region (x0,y0)-(x1,y1) in fractions of frame."""
    start_col = max(1, int(x0 * SAMPLE_WIDTH))
    end_col = min(SAMPLE_WIDTH, int(x1 * SAMPLE_WIDTH))
    start_row = max(0, int(y0 * SAMPLE_HEIGHT))
    end_row = min(SAMPLE_HEIGHT, int(y1 * SAMPLE_HEIGHT))
    total = 0.0
    count = 0
    for row in range(start_row, end_row):
        offset = row * SAMPLE_WIDTH * 3
        for col in range(start_col, end_col):
            i = offset + col * 3
            prev = offset + (col - 1) * 3
            diff = (
                abs(frame[i] - frame[prev])
                + abs(frame[i + 1] - frame[prev + 1])
                + abs(frame[i + 2] - frame[prev + 2])
            ) / 3.0
            total += diff
            count += 1
    if count == 0:
        return 0.0
    return total / (count * 255.0)


def _border_density(
    data: bytes, x0: float, y0: float, x1: float, y1: float, thickness: int = 2
) -> float:
    """Max-gradient along the border ring of a region (horizontal + vertical)."""
    start_col = max(1, int(x0 * SAMPLE_WIDTH))
    end_col = min(SAMPLE_WIDTH, int(x1 * SAMPLE_WIDTH))
    start_row = max(0, int(y0 * SAMPLE_HEIGHT))
    end_row = min(SAMPLE_HEIGHT, int(y1 * SAMPLE_HEIGHT))
    total = 0.0
    count = 0
    for row in range(start_row, end_row):
        offset = row * SAMPLE_WIDTH * 3
        on_ring = row < start_row + thickness or row >= end_row - thickness
        for col in range(start_col, end_col):
            on_border = on_ring or col < start_col + thickness or col >= end_col - thickness
            if not on_border:
                continue
            i = offset + col * 3
            diffs = []
            if col > 0:
                prev = offset + (col - 1) * 3
                diffs.append(
                    (
                        abs(data[i] - data[prev])
                        + abs(data[i + 1] - data[prev + 1])
                        + abs(data[i + 2] - data[prev + 2])
                    )
                    / 3.0
                )
            if col < SAMPLE_WIDTH - 1:
                nxt = offset + (col + 1) * 3
                diffs.append(
                    (
                        abs(data[i] - data[nxt])
                        + abs(data[i + 1] - data[nxt + 1])
                        + abs(data[i + 2] - data[nxt + 2])
                    )
                    / 3.0
                )
            if row > 0:
                up = (row - 1) * SAMPLE_WIDTH * 3 + col * 3
                diffs.append(
                    (
                        abs(data[i] - data[up])
                        + abs(data[i + 1] - data[up + 1])
                        + abs(data[i + 2] - data[up + 2])
                    )
                    / 3.0
                )
            if row < SAMPLE_HEIGHT - 1:
                down = (row + 1) * SAMPLE_WIDTH * 3 + col * 3
                diffs.append(
                    (
                        abs(data[i] - data[down])
                        + abs(data[i + 1] - data[down + 1])
                        + abs(data[i + 2] - data[down + 2])
                    )
                    / 3.0
                )
            if diffs:
                total += max(diffs)
                count += 1
    if count == 0:
        return 0.0
    return total / (count * 255.0)


def analyze_frames(
    frame_files: list[Path],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Analyze sampled frames; returns labels, scores, confidence, metrics."""
    if not frame_files:
        return {
            "status": LABEL_UNAVAILABLE,
            "labels": [],
            "metrics": {},
            "ocr_status": "unavailable",
            "note": "frame sampling produced no frames",
        }
    ocr_tool = config.get("ocr_tool")
    if ocr_tool:
        resolved = resolve_registered_tool(str(ocr_tool))
        if resolved is None:
            return {
                "status": LABEL_UNAVAILABLE,
                "labels": [],
                "metrics": {},
                "ocr_status": "unavailable",
                "note": f"configured OCR tool '{ocr_tool}' not found",
            }

    warning = float(config["text_area_warning_threshold"])
    reject = float(config["text_area_reject_threshold"])
    subtitle_persistence = float(config["subtitle_persistence_threshold"])
    watermark_persistence = float(config["watermark_persistence_threshold"])

    bottom = []
    top = []
    corners = {"tl": [], "tr": [], "bl": [], "br": []}
    center = []
    center_border = []
    full = []
    for frame_file in frame_files:
        data = frame_file.read_bytes()
        expected = SAMPLE_WIDTH * SAMPLE_HEIGHT * 3
        if len(data) < expected:
            continue
        payload = data[:expected]
        full.append(_edge_density(payload))
        bottom.append(_region_density(payload, 0.0, 0.75, 1.0, 1.0))
        top.append(_region_density(payload, 0.0, 0.0, 1.0, 0.15))
        corners["tl"].append(_region_density(payload, 0.0, 0.0, 0.1, 0.1))
        corners["tr"].append(_region_density(payload, 0.9, 0.0, 1.0, 0.1))
        corners["bl"].append(_region_density(payload, 0.0, 0.9, 0.1, 1.0))
        corners["br"].append(_region_density(payload, 0.9, 0.9, 1.0, 1.0))
        center.append(_region_density(payload, 0.3, 0.3, 0.7, 0.7))
        center_border.append(_border_density(payload, 0.3, 0.3, 0.7, 0.7))

    def average(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    def persistence(values: list[float], threshold: float) -> float:
        if not values:
            return 0.0
        return sum(1 for v in values if v >= threshold) / len(values)

    metrics = {
        "frames_analyzed": len(full),
        "full_edge_density": round(average(full), 4),
        "bottom_band_density": round(average(bottom), 4),
        "top_band_density": round(average(top), 4),
        "corner_density": {name: round(average(values), 4) for name, values in corners.items()},
        "center_density": round(average(center), 4),
        "center_border_density": round(average(center_border), 4),
        "subtitle_persistence": round(persistence(bottom, warning), 4),
        "watermark_persistence": round(
            persistence(
                [max(v) for v in zip(*corners.values())] if corners["tl"] else [],
                warning,
            ),
            4,
        ),
    }

    labels: list[dict[str, Any]] = []

    def add(label: str, score: float) -> None:
        confidence = min(1.0, max(0.0, score))
        labels.append(
            {"label": label, "score": round(score, 3), "confidence": round(confidence, 3)}
        )

    avg_bottom = average(bottom)
    if avg_bottom >= warning and metrics["subtitle_persistence"] >= subtitle_persistence:
        add(LABEL_SUBTITLES, min(1.0, avg_bottom / reject))
    corner_max = metrics["corner_density"]
    max_corner = max(corner_max.values()) if corner_max else 0.0
    if max_corner >= warning and metrics["watermark_persistence"] >= watermark_persistence:
        add(LABEL_WATERMARK, min(1.0, max_corner / reject))
    avg_full = average(full)
    if avg_full >= reject:
        add(LABEL_TEXT_HEAVY, min(1.0, avg_full / 1.0))
    avg_center = average(center)
    avg_border = average(center_border)
    if avg_border >= warning and avg_center < avg_border * 0.5:
        add(LABEL_PIP, min(1.0, avg_border / reject))
        add(LABEL_COMMENTARY, 0.4)

    status = LABEL_CLEAN if not labels else labels[0]["label"]
    return {
        "status": status,
        "labels": labels,
        "metrics": metrics,
        "ocr_status": "heuristic" if not ocr_tool else "ocr",
        "config_snapshot": {k: v for k, v in config.items() if k != "ocr_tool"},
    }


def analyze_media(
    media_path: Path,
    work_dir: Path,
    config: dict[str, Any] | None = None,
    runner: ProcessRunner | None = None,
) -> dict[str, Any]:
    """Full pipeline: validate config, sample frames (bounded), analyze."""
    try:
        effective = validate_visual_config(config)
    except ValueError as error:
        return {
            "status": LABEL_UNAVAILABLE,
            "labels": [],
            "metrics": {},
            "ocr_status": "unavailable",
            "note": f"invalid visual config: {error}",
        }
    started = time.monotonic()
    frames = sample_frames(media_path, work_dir, effective, runner=runner)
    if frames is None:
        return {
            "status": LABEL_UNAVAILABLE,
            "labels": [],
            "metrics": {},
            "ocr_status": "unavailable",
            "note": "ffmpeg unavailable or frame sampling failed",
        }
    result = analyze_frames(frames, effective)
    result["elapsed_seconds"] = round(time.monotonic() - started, 2)
    if not effective.get("retain_debug_frames"):
        for frame in frames:
            try:
                frame.unlink(missing_ok=True)
            except OSError:
                pass
    return result


def _load_config_from_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_ffmpeg_tool() -> Path | None:
    return _resolve_ffmpeg()
