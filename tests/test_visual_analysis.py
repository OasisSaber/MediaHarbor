from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from visual_analysis import (
    DEFAULT_VISUAL_CONFIG,
    LABEL_CLEAN,
    LABEL_COMMENTARY,
    LABEL_PIP,
    LABEL_SUBTITLES,
    LABEL_UNAVAILABLE,
    LABEL_WATERMARK,
    analyze_frames,
    validate_visual_config,
)

W = 160
H = 90


def _solid_frame(color: int = 128) -> bytes:
    return bytes([color]) * (W * H * 3)


def _bottom_band_frame() -> bytes:
    data = bytearray(_solid_frame())
    for row in range(int(H * 0.75), H):
        offset = row * W * 3
        for col in range(W):
            value = 255 if (col // 2) % 2 == 0 else 0
            data[offset + col * 3 : offset + col * 3 + 3] = bytes([value, value, value])
    return bytes(data)


def _corner_logo_frame() -> bytes:
    data = bytearray(_solid_frame())
    for row in range(int(H * 0.0), int(H * 0.1)):
        offset = row * W * 3
        for col in range(int(W * 0.0), int(W * 0.1)):
            value = 255 if (col // 2) % 2 == 0 else 0
            data[offset + col * 3 : offset + col * 3 + 3] = bytes([value, value, value])
    return bytes(data)


def _pip_frame() -> bytes:
    data = bytearray(_solid_frame())
    for row in range(int(H * 0.3), int(H * 0.7)):
        offset = row * W * 3
        for col in range(int(W * 0.3), int(W * 0.7)):
            data[offset + col * 3 : offset + col * 3 + 3] = bytes([40, 40, 40])
    return bytes(data)


def _write_frames(tmp: str, frames: list[bytes]) -> list[Path]:
    directory = Path(tmp)
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for index, frame in enumerate(frames):
        path = directory / f"f{index}.rgb"
        path.write_bytes(frame)
        paths.append(path)
    return paths


def test_validate_config_defaults_and_validation():
    assert validate_visual_config(None) == DEFAULT_VISUAL_CONFIG
    with pytest.raises(ValueError, match="frame_count"):
        validate_visual_config({"frame_count": 0})
    with pytest.raises(ValueError, match="frame_count"):
        validate_visual_config({"frame_count": 99})
    with pytest.raises(ValueError, match="text_area"):
        validate_visual_config({"text_area_warning_threshold": -1})
    with pytest.raises(ValueError, match="retain_debug_frames"):
        validate_visual_config({"retain_debug_frames": "yes"})
    with pytest.raises(ValueError, match="ocr_tool"):
        validate_visual_config({"ocr_tool": 5})


def test_persistent_bottom_band_is_subtitle_risk():
    with tempfile.TemporaryDirectory() as tmp:
        frames = _write_frames(tmp, [_bottom_band_frame()] * 6)
        result = analyze_frames(frames, DEFAULT_VISUAL_CONFIG)
        labels = {item["label"] for item in result["labels"]}
        assert LABEL_SUBTITLES in labels
        assert result["status"] == LABEL_SUBTITLES
        assert result["metrics"]["subtitle_persistence"] >= 0.5


def test_corner_logo_is_watermark_risk():
    with tempfile.TemporaryDirectory() as tmp:
        frames = _write_frames(tmp, [_corner_logo_frame()] * 6)
        result = analyze_frames(frames, DEFAULT_VISUAL_CONFIG)
        labels = {item["label"] for item in result["labels"]}
        assert LABEL_WATERMARK in labels
        assert result["status"] == LABEL_WATERMARK


def test_clean_solid_frames_are_clean():
    with tempfile.TemporaryDirectory() as tmp:
        frames = _write_frames(tmp, [_solid_frame()] * 6)
        result = analyze_frames(frames, DEFAULT_VISUAL_CONFIG)
        assert result["status"] == LABEL_CLEAN
        assert result["labels"] == []


def test_pip_layout_gets_panel_label():
    with tempfile.TemporaryDirectory() as tmp:
        frames = _write_frames(tmp, [_pip_frame()] * 6)
        result = analyze_frames(frames, DEFAULT_VISUAL_CONFIG)
        labels = {item["label"] for item in result["labels"]}
        assert LABEL_PIP in labels or LABEL_COMMENTARY in labels
        assert result["status"] in (LABEL_PIP, LABEL_COMMENTARY)


def test_no_frames_is_unavailable():
    result = analyze_frames([], DEFAULT_VISUAL_CONFIG)
    assert result["status"] == LABEL_UNAVAILABLE


def test_configured_ocr_missing_is_unavailable(tmp_path):
    import json as _json

    root = tmp_path
    (root / "AGENT_READ_ME_FIRST.md").write_text("")
    (root / "download-tools").mkdir(parents=True)
    (root / "download-tools" / "tools.json").write_text(
        _json.dumps(
            {
                "schema_version": 1,
                "tools": {"d": {"roles": ["t"], "platforms": {"windows-x64": "d/d.exe"}}},
            }
        )
    )
    (root / "skill" / "bagitup").mkdir(parents=True)
    (root / "skill" / "bagitup" / "SKILL.md").write_text("---\ntitle: test\n---\n")
    import os

    cwd = Path.cwd()
    try:
        os.chdir(root)
        with tempfile.TemporaryDirectory() as tmp:
            frames = _write_frames(tmp, [_solid_frame()] * 2)
            config = dict(DEFAULT_VISUAL_CONFIG)
            config["ocr_tool"] = "missing-ocr"
            result = analyze_frames(frames, config)
            assert result["status"] == LABEL_UNAVAILABLE
            assert "not found" in result["note"]
    finally:
        os.chdir(cwd)
