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

        # Settings panel signals
        settings_panel = self.view.get_settings_panel()
        if hasattr(settings_panel, 'save_requested'):
            settings_panel.save_requested.connect(self._on_save_settings)
        if hasattr(settings_panel, 'reset_requested'):
            settings_panel.reset_requested.connect(self._on_reset_settings)

        # Database panel signals
        database_panel = self.view.get_database_panel()
        if hasattr(database_panel, 'backup_requested'):
            database_panel.backup_requested.connect(self._on_backup_database)
        if hasattr(database_panel, 'restore_requested'):
            database_panel.restore_requested.connect(self._on_restore_database)

        # Logs panel signals
        logs_panel = self.view.get_logs_panel()
        if hasattr(logs_panel, 'refresh_requested'):
            logs_panel.refresh_requested.connect(self._on_refresh_logs)

        # AI Assistant panel signals (TASK 8)
        ai_panel = self.view.get_ai_assistant_panel()
        if hasattr(ai_panel, 'test_requested'):
            ai_panel.test_requested.connect(self._on_test_ai_tariff)

    def _load_initial_data(self):
        """Učitaj inicijalne podatke pri pokretanju."""
        # Load plugin data
        self._refresh_plugin_list()

        # Load system info
        self._refresh_system_info()

        # Load settings
        self._refresh_settings()

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

    # SETTINGS HANDLERS

    def _on_save_settings(self, settings: dict):
        """
        Handler za čuvanje settings-a.

        Args:
            settings: Dictionary sa settings-ima
        """
        try:
            # 1. Validiraj settings prije čuvanja
            if not self.service.settings_service.validate_settings(settings):
                self.view.get_settings_panel().show_error(
                    "Validacija settings-a nije uspjela!\n\n"
                    "Provjeri da su sve vrijednosti ispravne."
                )
                return

            # 2. Provjeri da li se bitne vrijednosti mijenjaju
            current_settings = self.service.get_settings()
            changes = []
            
            if current_settings.get('language') != settings.get('language'):
                changes.append(" Jezik zahtijeva restart aplikacije.")
            
            if current_settings.get('theme') != settings.get('theme'):
                changes.append(" Tema zahtijeva restart aplikacije.")

            # 3. Prikaži upozorenje ako treba restart
            if changes:
                reply = self.confirm(
                    "Da li želiš da nastaviš?",
                    "Promjena settings-a"
                )

                if not reply:
                    return

            # 4. Sačuvaj settings sa backup-om
            success = self.service.save_settings(settings, create_backup=True)

            if success:
                # Prikaži šta je sačuvano
                details = "\n".join([f"  • {key}: {value}" for key, value in settings.items()])
                
                self.view.get_settings_panel().show_success(
                    "Settings uspješno sačuvani!\n\n" +
                    f"Sauvano:\n{details}\n\n" +
                    "Backup kreiran automatski."
                )
                
                # Refresh UI
                self._refresh_settings()
            else:
                self.view.get_settings_panel().show_error(
                    "Čuvanje settings-a nije uspjelo!\n\n"
                    "Provjeri da li imaš dozvolu za pisanje fajla."
                )
        except Exception as e:
            self.view.get_settings_panel().show_error(
                f"Greška pri čuvanju:\n{str(e)}"
            )

    def _refresh_settings(self):
        """Refresh settings-a."""
        settings = self.service.get_settings()
        self.view.get_settings_panel().set_settings(settings)

    def _on_reset_settings(self):
        """Handler za reset settings-a na default."""
        try:
            reply = self.confirm_destructive_action(
                "Da li zaista želiš da resetuješ settings na fabrička podešavanja?\n\n"
                "Ova akcija će poništiti sve tvoje izmjene.",
                "Potvrda"
            )

            if not reply:
                return

            success = self.service.settings_service.reset_to_defaults()

            if success:
                self.view.get_settings_panel().show_success(
                    "Settings su resetovani na fabrička podešavanja!\n\n"
                    "Neki settings zahtijevaju restart aplikacije."
                )
                self._refresh_settings()
            else:
                self.view.get_settings_panel().show_error(
                    "Reset settings-a nije uspio!"
                )
        except Exception as e:
            self.view.get_settings_panel().show_error(
                f"Greška pri reset-u:\n{str(e)}"
            )

    # DATABASE HANDLERS

    def _on_backup_database(self, backup_path: str):
        """
        Handler za database backup.

        Args:
            backup_path: Put gdje sačuvati backup
        """
        try:
            success = self.service.create_backup(backup_path)

            if success:
                self.view.get_database_panel().show_success(
                    f"Backup kreiran: {backup_path}"
                )
            else:
                self.view.get_database_panel().show_error(
                    "Kreiranje backup-a nije uspjelo!"
                )
        except Exception as e:
            self.view.get_database_panel().show_error(
                f"Greška pri backup-u: {e}"
            )

    def _on_restore_database(self, backup_path: str):
        """
        Handler za obnovu baze.

        Args:
            backup_path: Put do backup fajla
        """
        try:
            success = self.service.restore_backup(backup_path)

            if success:
                self.view.get_database_panel().show_success(
                    "Baza uspešno obnovljena!"
                )
            else:
                self.view.get_database_panel().show_error(
                    "Obnova baze nije uspela!"
                )
        except Exception as e:
            self.view.get_database_panel().show_error(
                f"Greška pri obnovi: {e}"
            )

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

    # AI ASSISTANT HANDLERS (TASK 8)

    def _on_test_ai_tariff(self, naziv_robe: str):
        """
        Handler za testiranje AI tarifnog prijedloga.

        Args:
            naziv_robe: Naziv robe za testiranje
        """
        try:
            from services.agent.hybrid_tariff_agent import HybridTariffAgent

            agent = HybridTariffAgent()
            result = agent.decide_tariff(naziv_robe)

            # Prikaži rezultate u AI Assistant panelu
            ai_panel = self.view.get_ai_assistant_panel()
            ai_panel.display_results(result)

        except Exception as e:
            ai_panel = self.view.get_ai_assistant_panel()
            ai_panel.display_error(f"Greška pri AI prijedlogu: {e}")
