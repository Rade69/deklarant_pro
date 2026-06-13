from gui.utils.display_profile import build_display_key, classify_display


def test_classify_display_uses_logical_available_size():
    assert classify_display(1536, 816).name == "compact"
    assert classify_display(1920, 1032).name == "standard"
    assert classify_display(3440, 1400).name == "large"


def test_display_key_changes_with_monitor_or_windows_scale():
    laptop = build_display_key("DISPLAY1", 1536, 816, 1.25, model="Laptop")
    external = build_display_key("DISPLAY2", 1920, 1032, 1.0, model="VX239")
    external_scaled = build_display_key("DISPLAY2", 1536, 826, 1.25, model="VX239")

    assert laptop != external
    assert external != external_scaled


def test_display_key_is_stable_for_same_signature():
    first = build_display_key("DISPLAY2", 1920, 1032, 1.0, "ASUS", "VX239")
    second = build_display_key("DISPLAY2", 1920, 1032, 1.0, "ASUS", "VX239")

    assert first == second
