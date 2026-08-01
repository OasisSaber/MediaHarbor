from __future__ import annotations

from provenance import MIN_PROVENANCE_THRESHOLD, reasons_to_messages, score_candidate


def test_official_source_preferred():
    score, reasons = score_candidate(
        "Full speech by Minister 2026",
        "Ministry of Culture",
        3600.0,
        False,
        False,
    )
    assert score > MIN_PROVENANCE_THRESHOLD
    assert any("official" in r or "channel" in r for r in reasons)


def test_commentary_down_ranked():
    score, reasons = score_candidate(
        "EXPLAINER: What happened at the summit",
        "Some Commentary Channel",
        900.0,
        False,
        False,
    )
    assert score < MIN_PROVENANCE_THRESHOLD
    assert any("commentary" in r or "edit" in r for r in reasons)


def test_short_form_down_ranked():
    score, _ = score_candidate(
        "Quick clip",
        "Someone",
        30.0,
        False,
        False,
    )
    assert score < MIN_PROVENANCE_THRESHOLD


def test_duplicate_down_ranked():
    score, reasons = score_candidate(
        "Official archive recording",
        "National Archive",
        1800.0,
        False,
        True,
    )
    assert any("duplicate" in r for r in reasons)


def test_deterministic():
    args = ("Full press conference", "Broadcast News", 7200.0, False, False)
    first = score_candidate(*args)
    second = score_candidate(*args)
    assert first == second


def test_reasons_to_messages_maps_all_codes():
    codes = [
        "positive:official-or-archival-signals",
        "positive:official-channel",
        "positive:live-recording",
        "negative:commentary-or-edit-signals",
        "negative:short-form-duration",
        "negative:duplicate-candidate",
    ]
    messages = reasons_to_messages(codes)
    assert len(messages) == len(codes)
    assert all(m != code for m, code in zip(messages, codes))
