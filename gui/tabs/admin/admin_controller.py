"""
Admin Controller - Orchestration layer.

Koordinira View i Service layer-e.
"""

from typing import Optional
from gui.tabs.base_controller import BaseTabController
from gui.tabs.admin.admin_view import AdminView
from services.admin.admin_service import AdminService


class AdminController(BaseTabController):
    """
    Admin Controller - orchestration layer.

    Povezuje View events sa Service operations.
    """

    def __init__(self, view: AdminView, service: AdminService):
        """
        Inicijalizacija.

        Args:
            view: AdminView instance
            service: AdminService instance
        """
        super().__init__(view, service)
        self.view = view
        self.service = service

        # Connect signals
        self._connect_signals()

        # Initial data load
        self._load_initial_data()

    def _connect_signals(self):
        """Povezivanje View signala sa handler metodama."""
        # Plugin panel signals
        plugin_panel = self.view.get_plugin_panel()
        if hasattr(plugin_panel, 'install_requested'):
            plugin_panel.install_requested.connect(self._on_install_plugin)
        if hasattr(plugin_panel, 'reload_requested'):
            plugin_panel.reload_requested.connect(self._on_reload_plugins)
        if hasattr(plugin_panel, 'remove_requested'):
            plugin_panel.remove_requested.connect(self._on_remove_plugin)

        # Logs panel signals
        logs_panel = self.view.get_logs_panel()
        if hasattr(logs_panel, 'refresh_requested'):
            logs_panel.refresh_requested.connect(self._on_refresh_logs)

        # System panel signals
        system_panel = self.view.get_system_panel()
        if hasattr(system_panel, 'refresh_requested'):
            system_panel.refresh_requested.connect(self._refresh_system_info)

        settings_panel = self.view.get_settings_panel()
        settings_panel.save_requested.connect(self._on_save_settings)
        settings_panel.reset_requested.connect(self._on_reset_settings)
        settings_panel.test_sound_requested.connect(self._on_test_sound)

    def _load_initial_data(self):
        """Učitaj inicijalne podatke pri pokretanju."""
        # Load plugin data
        self._refresh_plugin_list()

        # Load system info
        self._refresh_system_info()

        self.view.get_settings_panel().set_settings(self.service.get_settings())

    def _on_save_settings(self, settings: dict):
        panel = self.view.get_settings_panel()
        if self.service.save_settings(settings):
            panel.show_success("Podešavanja su uspješno sačuvana.")
        else:
            panel.show_error("Podešavanja nisu sačuvana.")

    def _on_reset_settings(self):
        panel = self.view.get_settings_panel()
        if self.service.reset_settings():
            panel.set_settings(self.service.get_settings())
            panel.show_success("Podešavanja su vraćena na fabričke vrijednosti.")
        else:
            panel.show_error("Podešavanja nije moguće resetovati.")

    def _on_test_sound(self):
        from services.process_completion_sound import play_process_completion_sound

        if not play_process_completion_sound("success", force=True):
            self.view.get_settings_panel().show_error(
                "Probni zvuk nije moguće reprodukovati."
            )

    # PLUGIN HANDLERS

    def _on_install_plugin(self, filepath: str):
        """
        Handler za instalaciju plugin-a.

        Args:
            filepath: Put do .py fajla
        """
        try:
            # Provjeri da fajl već postoji
            from pathlib import Path
            dest_path = self.service.plugin_loader.parsers_dir / Path(filepath).name

            if dest_path.exists():
                # Pitaj usera da li da overwrite-uje
                reply = self.confirm_destructive_action(
                    f"Da li želiš da ga zamijeniš novim?",
                    "Fajl već postoji"
                )

                if not reply:
                    return

            success = self.service.install_plugin(filepath)

            if success:
                self.view.get_plugin_panel().show_success(
                    "Plugin uspješno instaliran!\n\n"
                    f"Fajl: {Path(filepath).name}\n"
                    "Lokacija: plugins/parsers/\n\n"
                    "Klikni 'Ponovo učitaj parsere' da aktiviraš novi parser."
                )
                self._refresh_plugin_list()
            else:
                self.view.get_plugin_panel().show_error(
                    "Instalacija plugin-a nije uspjela!\n\n"
                    "Provjeri da je fajl validan Python parser."
                )
        except Exception as e:
            self.view.get_plugin_panel().show_error(
                f"Greška pri instalaciji:\n{str(e)}"
            )

    def _on_reload_plugins(self):
        """Handler za reload plugin-a."""
        try:
            self.service.reload_plugins()
            self._refresh_plugin_list()
            
            # Prikaži broj ponovo učitanih parsera
            plugins = self.service.get_installed_plugins()
            
            self.view.get_plugin_panel().show_success(
                f"Plugin-i uspješno ponovo učitani!\n\n"
                f"Ukupno parsera: {len(plugins)}\n\n"
                f"Svi parseri su ponovo učitani iz registry-ja.\n"
                f"Novi parseri su sada aktivni."
            )
        except Exception as e:
            self.view.get_plugin_panel().show_error(
                f"Greška pri ponovnom učitavanju:\n{str(e)}"
            )

    def _on_remove_plugin(self, plugin_name: str):
        """
        Handler za uklanjanje plugin-a.

        Args:
            plugin_name: Ime plugin-a za uklanjanje
        """
        try:
            # Provjeri da li parser postoji
            plugin_info = self.service.get_parser_info(plugin_name)
            
            if not plugin_info:
                self.view.get_plugin_panel().show_error(
                    f"Parser '{plugin_name}' nije pronađen!"
                )
                return

            success = self.service.remove_plugin(plugin_name)

            if success:
                self.view.get_plugin_panel().show_success(
                    f"Plugin '{plugin_name}' je uspješno uklonjen!\n\n"
                    f"Fajl: {plugin_info['filename']}\n"
                    f"Lokacija: plugins/parsers/\n\n"
                    f"Klikni 'Ponovo učitaj parsere' da osvježiš listu."
                )
                self._refresh_plugin_list()
            else:
                self.view.get_plugin_panel().show_error(
                    f"Uklanjanje plugin-a '{plugin_name}' nije uspjelo!\n\n"
                    "Provjeri da li imaš dozvolu za brisanje fajla."
                )
        except Exception as e:
            self.view.get_plugin_panel().show_error(
                f"Greška pri uklanjanju:\n{str(e)}"
            )

    def _refresh_plugin_list(self):
        """Refresh liste plugin-a."""
        plugins = self.service.get_installed_plugins()
        self.view.get_plugin_panel().set_plugins(plugins)

    # LOGS HANDLERS

    def _on_refresh_logs(self):
        """Handler za refresh log-ova."""
        try:
            logs = self.service.get_recent_logs()
            self.view.get_logs_panel().set_logs(logs)
        except Exception as e:
            self.view.get_logs_panel().show_error(
                f"Greška pri učitavanju log-ova: {e}"
            )

    # SYSTEM INFO

    def _refresh_system_info(self):
        """Refresh system info-a."""
        system_info = self.service.get_system_info()
        self.view.get_system_panel().set_system_info(system_info)
