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
        "positive:cn-official-or-archival-signals",
        "positive:official-channel",
        "positive:cn-official-channel",
        "positive:live-recording",
        "negative:commentary-or-edit-signals",
        "negative:cn-commentary-or-edit-signals",
        "negative:short-form-duration",
        "negative:duplicate-candidate",
    ]
    messages = reasons_to_messages(codes)
    assert len(messages) == len(codes)
    assert all(m != code for m, code in zip(messages, codes))


def test_cn_official_signals_boost():
    score, reasons = score_candidate(
        "嫦娥六号发射全程直播 官方现场",
        "央视新闻",
        600.0,
        False,
        False,
    )
    assert score > MIN_PROVENANCE_THRESHOLD
    assert any("cn-official" in r or "cn-official-channel" in r for r in reasons)


def test_cn_commentary_down_ranked():
    score, reasons = score_candidate(
        "火箭发射解说合集",
        "某UP主",
        900.0,
        False,
        False,
    )
    assert score < MIN_PROVENANCE_THRESHOLD
    assert any("cn-commentary" in r for r in reasons)


def test_cn_short_form_down_ranked():
    score, _ = score_candidate(
        "发射现场短视频",
        "某人",
        30.0,
        False,
        False,
    )
    assert score < MIN_PROVENANCE_THRESHOLD


def test_cn_no_clip_does_not_trigger_negative():
    # "无剪辑" is a positive signal; bare "剪辑" must not be a negative term.
    score, reasons = score_candidate(
        "长征五号发射全程无剪辑",
        "路人甲",
        600.0,
        False,
        False,
    )
    assert score > MIN_PROVENANCE_THRESHOLD
    assert any("positive" in r for r in reasons)
    assert not any("negative" in r for r in reasons)
