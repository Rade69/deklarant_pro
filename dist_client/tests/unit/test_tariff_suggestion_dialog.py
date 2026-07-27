from gui.dialogs.tariff_suggestion_dialog import (
    _format_similarity,
    _tariff_change_profile,
)


def test_format_similarity_clamps_over_100_percent():
    assert _format_similarity(1.10) == "100%"


def test_format_similarity_clamps_negative_percent():
    assert _format_similarity(-0.25) == "0%"


def test_tariff_change_profile_marks_same_heading_as_low_risk():
    profile = _tariff_change_profile("84818090", "84818081")

    assert profile["level"] == "low"
    assert profile["apply_default"] is True


def test_tariff_change_profile_marks_same_chapter_as_medium_risk():
    profile = _tariff_change_profile("84818090", "84139100")

    assert profile["level"] == "medium"
    assert profile["apply_default"] is False


def test_tariff_change_profile_marks_different_chapter_as_high_risk():
    profile = _tariff_change_profile("21069092", "17049081")

    assert profile["level"] == "high"
    assert profile["apply_default"] is False


def test_tariff_change_profile_does_not_default_apply_when_same_code():
    profile = _tariff_change_profile("84818090", "84818090")

    assert profile["level"] == "same"
    assert profile["apply_default"] is False
