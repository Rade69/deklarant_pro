from config.settings import get_path_settings


def test_admin_stylesheet_uses_active_palette():
    stylesheet = (
        get_path_settings().styles_dir / "admin_tab.qss"
    ).read_text(encoding="utf-8")

    assert "QListWidget#AdminNavigation::item:hover" in stylesheet
    assert "background-color: #d8e5ed;" in stylesheet
    assert "background-color: #3477a5;" in stylesheet
    assert "color: #17324a;" in stylesheet
    assert "#5a8060" not in stylesheet
    assert "#c8dcc8" not in stylesheet


def test_admin_stylesheet_matches_dist_client():
    root_stylesheet = (
        get_path_settings().styles_dir / "admin_tab.qss"
    ).read_text(encoding="utf-8")
    dist_stylesheet = (
        get_path_settings().project_root
        / "dist_client"
        / "styles"
        / "admin_tab.qss"
    ).read_text(encoding="utf-8")

    assert root_stylesheet == dist_stylesheet
