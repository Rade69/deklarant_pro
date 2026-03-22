# gui/tabs/tab_factory.py

"""
Factory pattern za kreiranje tabova sa Dependency Injection.
Centralizovano kreiranje tabova - svaki tab dobija refaktorisane Service i Controller slojeve.
"""

import logging
from typing import Optional, Callable, Dict, Any
from PySide6.QtWidgets import QWidget

from core.draft.draft import DeclarationDraft
from utils.dependency_injection import get_di_container, register_services

# Import refaktorisanih tab klasa
from gui.tabs.zaglavlje_tab_refactored import ZaglavljeTabRefactored
from gui.tabs.faktura_tab_refactored import FakturaTabRefactored
from gui.tabs.naimenovanja_tab_refactored import NaimenovanjaTabRefactored
from gui.tabs.sifarnici_tab_refactored import SifarniciTabRefactored

# Import refaktorisanih service klasa (za DI registraciju)
from services.zaglavlje_service_refactored import ZaglavljeService
from services.faktura_service_refactored import FakturaService
from services.naimenovanja_service_refactored import NaimenovanjaService
from services.sifarnici_service_refactored import SifarniciService


logger = logging.getLogger(__name__)


class TabFactory:
    """
    Factory za kreiranje tabova sa Dependency Injection.

    Odgovornosti:
    - Inicijalizacija DI containera sa svim servisima
    - Kreiranje tabova (View + Controller + Service)
    - Singleton servisi kroz DI container
    - Caching tab instanci (opciono)
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._cache: Dict[str, QWidget] = {}

        # Inicijalizuj DI container sa svim servisima
        self._container = get_di_container()
        self._register_services()

    def _register_services(self):
        """Registruj sve servise u DI container kao singletone."""
        try:
            if not self._container.has_service(ZaglavljeService):
                self._container.register_singleton(ZaglavljeService, ZaglavljeService)
            if not self._container.has_service(FakturaService):
                self._container.register_singleton(FakturaService, FakturaService)
            if not self._container.has_service(NaimenovanjaService):
                self._container.register_singleton(NaimenovanjaService, NaimenovanjaService)
            if not self._container.has_service(SifarniciService):
                self._container.register_singleton(SifarniciService, SifarniciService)
            self.logger.info("✅ DI container: svi servisi registrovani")
        except Exception as e:
            self.logger.warning(f"⚠️ DI container registracija: {e}")

    def create_tab(self,
                   tab_type: str,
                   draft: Optional[DeclarationDraft] = None,
                   on_dirty: Optional[Callable] = None,
                   parent: Optional[QWidget] = None,
                   **kwargs) -> Optional[QWidget]:
        """
        Kreiraj tab odredjenog tipa.

        Args:
            tab_type: Tip taba ('zaglavlje', 'faktura', 'naimenovanja', 'sifarnici')
            draft: Početni draft (opciono)
            on_dirty: Callback za dirty state (opciono)
            parent: Parent widget (opciono)

        Returns:
            Kreirani tab widget ili None ako neuspješno
        """
        try:
            cache_key = self._get_cache_key(tab_type, draft, **kwargs)
            if cache_key in self._cache:
                self.logger.debug(f"Vraćam iz cache-a: {tab_type}")
                return self._cache[cache_key]

            if tab_type == 'zaglavlje':
                tab = self._create_zaglavlje_tab(draft, on_dirty, parent)
            elif tab_type == 'faktura':
                tab = self._create_faktura_tab(draft, on_dirty, parent)
            elif tab_type == 'naimenovanja':
                tab = self._create_naimenovanja_tab(draft, on_dirty, parent)
            elif tab_type == 'sifarnici':
                tab = self._create_sifarnici_tab(draft, on_dirty, parent)
            else:
                raise ValueError(f"Nepoznat tip taba: {tab_type}")

            self._cache[cache_key] = tab
            self.logger.info(f"✅ Kreiran tab: {tab_type}")
            return tab

        except Exception as e:
            self.logger.error(f"❌ Greška pri kreiranju taba {tab_type}: {e}")
            return None

    def _create_zaglavlje_tab(self,
                              draft: Optional[DeclarationDraft],
                              on_dirty: Optional[Callable],
                              parent: Optional[QWidget]) -> ZaglavljeTabRefactored:
        """Kreiraj ZaglavljeTab sa refaktorisanim servisom."""
        return ZaglavljeTabRefactored(draft=draft, on_dirty=on_dirty, parent=parent)

    def _create_faktura_tab(self,
                            draft: Optional[DeclarationDraft],
                            on_dirty: Optional[Callable],
                            parent: Optional[QWidget]) -> FakturaTabRefactored:
        """Kreiraj FakturaTab sa refaktorisanim servisom."""
        return FakturaTabRefactored(draft=draft, on_dirty=on_dirty, parent=parent)

    def _create_naimenovanja_tab(self,
                                 draft: Optional[DeclarationDraft],
                                 on_dirty: Optional[Callable],
                                 parent: Optional[QWidget]) -> NaimenovanjaTabRefactored:
        """Kreiraj NaimenovanjaTab sa refaktorisanim servisom."""
        return NaimenovanjaTabRefactored(draft=draft, on_dirty=on_dirty, parent=parent)

    def _create_sifarnici_tab(self,
                              draft: Optional[DeclarationDraft],
                              on_dirty: Optional[Callable],
                              parent: Optional[QWidget]) -> SifarniciTabRefactored:
        """Kreiraj SifarniciTab sa refaktorisanim servisom."""
        return SifarniciTabRefactored(draft=draft, on_dirty=on_dirty, parent=parent)

    def _get_cache_key(self,
                       tab_type: str,
                       draft: Optional[DeclarationDraft],
                       **kwargs) -> str:
        """Generiši cache key za tab."""
        key_parts = [tab_type]
        if draft:
            key_parts.append(f"draft_{id(draft)}")
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}_{v}")
        return "_".join(key_parts)

    def clear_cache(self, tab_type: str = None):
        """Očisti cache."""
        if tab_type:
            keys_to_delete = [k for k in self._cache.keys() if k.startswith(tab_type)]
            for key in keys_to_delete:
                del self._cache[key]
            self.logger.info(f"Očišćen cache za {tab_type}: {len(keys_to_delete)} stavki")
        else:
            count = len(self._cache)
            self._cache.clear()
            self.logger.info(f"Očišćen cache: {count} stavki")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Vrati statistiku cache-a."""
        stats = {'total': len(self._cache), 'by_type': {}}
        for key in self._cache.keys():
            tab_type = key.split('_')[0]
            stats['by_type'][tab_type] = stats['by_type'].get(tab_type, 0) + 1
        return stats

    def create_all_tabs(self,
                        draft: Optional[DeclarationDraft] = None,
                        on_dirty: Optional[Callable] = None,
                        parent: Optional[QWidget] = None) -> Dict[str, QWidget]:
        """Kreiraj sve tabove."""
        tabs = {}
        for tab_type in ['zaglavlje', 'faktura', 'naimenovanja', 'sifarnici']:
            tab = self.create_tab(tab_type=tab_type, draft=draft, on_dirty=on_dirty, parent=parent)
            if tab:
                tabs[tab_type] = tab
        return tabs

    def get_di_container(self):
        """Vrati DI container (za testiranje)."""
        return self._container


# Singleton instance
_tab_factory_instance = None


def get_tab_factory() -> TabFactory:
    """Vrati singleton instancu TabFactory."""
    global _tab_factory_instance
    if _tab_factory_instance is None:
        _tab_factory_instance = TabFactory()
    return _tab_factory_instance
