from __future__ import annotations

import pytest
from quality import (
    FORMAT_INFO_UNAVAILABLE,
    FORMAT_NO_QUALIFYING,
    FORMAT_OK,
    build_format_selector,
    default_quality_profile,
    evaluate_format_summary,
    evaluate_media_fields,
    validate_quality_profile,
)


def test_default_profile():
    profile = default_quality_profile()
    assert profile["minimum_height"] == 720
    assert profile["minimum_fps"] == 24
    assert profile["prefer_landscape"] is True
    assert profile["allow_below_minimum"] is False


def test_validate_profile_rejects_malformed():
    with pytest.raises(ValueError, match="minimum_height"):
        validate_quality_profile({"minimum_height": -1})
    with pytest.raises(ValueError, match="minimum_fps"):
        validate_quality_profile({"minimum_fps": "high"})
    with pytest.raises(ValueError, match="prefer_landscape"):
        validate_quality_profile({"prefer_landscape": "yes"})
    with pytest.raises(ValueError, match="preferred_height"):
        validate_quality_profile({"preferred_height": 480, "minimum_height": 720})


def test_validate_profile_accepts_none_and_partial():
    assert validate_quality_profile(None) == default_quality_profile()
    profile = validate_quality_profile({"minimum_fps": 30})
    assert profile["minimum_fps"] == 30
    assert profile["minimum_height"] == 720


def test_evaluate_format_summary_ok():
    summary = {"count": 3, "max_height": 1080, "max_fps": 60, "max_bitrate": 5000}
    status, reasons = evaluate_format_summary(summary, default_quality_profile())
    assert status == FORMAT_OK
    assert reasons


def test_evaluate_format_summary_no_qualifying():
    summary = {"count": 2, "max_height": 480, "max_fps": 30, "max_bitrate": 800}
    status, reasons = evaluate_format_summary(summary, default_quality_profile())
    assert status == FORMAT_NO_QUALIFYING
    assert any("height" in r for r in reasons)


def test_evaluate_format_summary_info_unavailable():
    assert evaluate_format_summary(None, default_quality_profile())[0] == FORMAT_INFO_UNAVAILABLE
    assert (
        evaluate_format_summary({"count": 0}, default_quality_profile())[0]
        == FORMAT_INFO_UNAVAILABLE
    )


def test_build_format_selector():
    assert build_format_selector(default_quality_profile()) == "bv*[height>=720][fps>=24]+ba/b"
    assert (
        build_format_selector(
            {"minimum_height": None, "minimum_fps": None, "minimum_video_bitrate": None}
        )
        == "bv*+ba/b"
    )
    below = default_quality_profile()
    below["allow_below_minimum"] = True
    assert build_format_selector(below) == "bv*[height>=720][fps>=24]/b"


def test_evaluate_media_fields():
    profile = default_quality_profile()
    assert (
        evaluate_media_fields(
            {"width": 1920, "height": 1080, "fps": 30.0, "video_bitrate": 5000}, profile
        )[0]
        == "PASS"
    )
    status, reasons = evaluate_media_fields(
        {"width": 640, "height": 360, "fps": 30.0, "video_bitrate": 5000}, profile
    )
    assert status == "REJECT"
    assert any("height" in r for r in reasons)
    status, reasons = evaluate_media_fields(
        {"width": 640, "height": 360, "fps": 30.0, "video_bitrate": 5000},
        {
            "minimum_height": 720,
            "minimum_fps": 24,
            "minimum_video_bitrate": None,
            "allow_vertical": True,
            "prefer_landscape": False,
            "allow_below_minimum": True,
            "preferred_height": 1080,
        },
    )
    assert status == "WARN"
    status, _ = evaluate_media_fields({"width": 720, "height": 1280, "fps": 30.0}, profile)
    assert status == "REJECT"
    assert evaluate_media_fields(None, profile)[0] == "UNKNOWN"


def test_build_format_selector_bitrate_only():
    assert build_format_selector({"minimum_video_bitrate": 2500}) == "bv*[vbr>=2500]+ba/b"


def test_build_format_selector_all_three_filters():
    assert (
        build_format_selector(
            {
                "minimum_height": 720,
                "minimum_fps": 24,
                "minimum_video_bitrate": 2500,
            }
        )
        == "bv*[height>=720][fps>=24][vbr>=2500]+ba/b"
    )


def test_build_format_selector_below_minimum_with_bitrate():
    assert (
        build_format_selector({"minimum_video_bitrate": 2500, "allow_below_minimum": True})
        == "bv*[vbr>=2500]/b"
    )
