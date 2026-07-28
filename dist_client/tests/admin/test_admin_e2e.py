"""
End-to-End Tests for Admin Tab.

Testovi za kompletan Admin Tab - integration i functional tests.
"""

import pytest
from PySide6.QtWidgets import QApplication
from services.admin.admin_service import AdminService


# Globalna QApplication instanca
_app = None


@pytest.fixture(scope='session')
def app():
    """Kreiraj QApplication za testove (singleton)."""
    global _app
    if _app is None:
        _app = QApplication([])
    return _app


@pytest.fixture
def admin_tab(app):
    """Kreiraj AdminTab za testove."""
    from gui.tabs.admin_tab import AdminTab
    return AdminTab()


@pytest.fixture
def admin_service():
    """Kreiraj AdminService za testove."""
    return AdminService()


class TestAdminService:
    """Testovi za AdminService."""

    def test_admin_service_created(self, admin_service):
        """Test da je AdminService kreiran."""
        assert admin_service is not None

    def test_admin_service_has_sub_services(self, admin_service):
        """Test da AdminService ima sve pod-servise."""
        assert admin_service.plugin_service is not None
        assert admin_service.settings_service is not None
        assert admin_service.backup_service is not None
        assert admin_service.log_service is not None
        assert admin_service.analytics_service is not None

    def test_get_system_info(self, admin_service):
        """Test get_system_info metode."""
        info = admin_service.get_system_info()
        
        assert isinstance(info, dict)
        assert 'app_name' in info
        assert 'app_version' in info
        assert 'python_version' in info
        assert 'platform' in info
        assert 'plugins_count' in info
        assert info['app_name'] == 'Deklarant Pro'

    def test_get_installed_plugins(self, admin_service):
        """Test get_installed_plugins metode."""
        plugins = admin_service.get_installed_plugins()
        assert isinstance(plugins, list)

    def test_get_settings(self, admin_service):
        """Test get_settings metode."""
        settings = admin_service.get_settings()
        assert isinstance(settings, dict)
        assert 'theme' in settings
        assert 'language' in settings

    def test_get_import_statistics(self, admin_service):
        """Test get_import_statistics metode."""
        stats = admin_service.get_import_statistics()
        assert isinstance(stats, dict)
        assert 'total_imports' in stats


class TestAdminView:
    """Testovi za AdminView."""

    def test_admin_view_created(self, app):
        """Test da je AdminView kreiran."""
        from gui.tabs.admin.admin_view import AdminView
        view = AdminView()
        assert view is not None

    def test_admin_view_has_panels(self, app):
        """Test da AdminView ima sve panele."""
        from gui.tabs.admin.admin_view import AdminView
        view = AdminView()
        
        assert view.get_plugin_panel() is not None
        assert view.get_settings_panel() is not None
        assert view.get_database_panel() is not None
        assert view.get_logs_panel() is not None
        assert view.get_system_panel() is not None
        assert view.get_analytics_panel() is not None

    def test_admin_view_sidebar_items(self, app):
        """Test da sidebar ima 7 stavki."""
        from gui.tabs.admin.admin_view import AdminView
        view = AdminView()
        assert view.nav_list.count() == 8

    def test_admin_view_content_panels(self, app):
        """Test da content stack ima 7 panela."""
        from gui.tabs.admin.admin_view import AdminView
        view = AdminView()
        assert view.content_stack.count() == 8


class TestAdminController:
    """Testovi za AdminController."""

    def test_admin_controller_created(self, app):
        """Test da je AdminController kreiran."""
        from gui.tabs.admin.admin_view import AdminView
        from gui.tabs.admin.admin_controller import AdminController
        
        view = AdminView()
        service = AdminService()
        controller = AdminController(view, service)
        
        assert controller is not None
        assert controller.view is not None
        assert controller.service is not None


class TestAdminTab:
    """Testovi za AdminTab."""

    def test_admin_tab_created(self, app):
        """Test da je AdminTab kreiran."""
        from gui.tabs.admin_tab import AdminTab
        tab = AdminTab()
        assert tab is not None

    def test_admin_tab_has_service(self, app):
        """Test da AdminTab ima service."""
        from gui.tabs.admin_tab import AdminTab
        tab = AdminTab()
        assert tab.service is not None

    def test_admin_tab_has_view(self, app):
        """Test da AdminTab ima view."""
        from gui.tabs.admin_tab import AdminTab
        tab = AdminTab()
        assert tab.view is not None

    def test_admin_tab_has_controller(self, app):
        """Test da AdminTab ima controller."""
        from gui.tabs.admin_tab import AdminTab
        tab = AdminTab()
        assert tab.controller is not None


class TestIntegration:
    """Integration testovi."""

    def test_full_admin_tab_workflow(self, app):
        """Test kompletnog workflow-a."""
        from gui.tabs.admin_tab import AdminTab
        
        # Kreiraj AdminTab
        admin_tab = AdminTab()
        
        # 1. Provjeri da su svi paneli dostupni
        view = admin_tab.view
        assert view.get_plugin_panel() is not None
        assert view.get_settings_panel() is not None
        
        # 2. Provjeri da servisi rade
        service = admin_tab.service
        info = service.get_system_info()
        assert info['app_name'] == 'Deklarant Pro'
        
        # 3. Provjeri da settings rade
        settings = service.get_settings()
        assert 'theme' in settings
        
        # 4. Provjeri da statistike rade
        stats = service.get_import_statistics()
        assert 'total_imports' in stats


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
