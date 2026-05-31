# importers/strategy_registry.py

"""
Strategy Registry Sistem za Import

Ovaj modul pruža centralizovani registry za upravljanje import strategijama.
Omogućava registraciju, automatsku selekciju i izvršavanje strategija.

Primjer korišćenja:
    from importers.strategy_registry import get_registry
    
    # Dobij global registry
    registry = get_registry()
    
    # Registruj strategiju
    registry.register(MyCustomStrategy())
    
    # Importuj fajl (automatski bira strategiju)
    result = registry.import_file(Path("faktura.xlsx"))
"""

from typing import List, Optional, Any
from pathlib import Path

from importers.base_strategy import ImportStrategy
from importers.exceptions import FileNotSupportedError


class StrategyRegistry:
    """
    Registry za import strategije.
    
    Upravlja registracijom, sortiranjem i selekcijom odgovarajuće
    strategije za dati fajl.
    
    Strategije se automatski sortiraju po prioritetu - strategije
    sa višim prioritetom se procjenjuju prve.
    
    Primjer:
        >>> registry = StrategyRegistry()
        >>> registry.register(ExcelStrategy())  # priority=0
        >>> registry.register(SpecificExcelStrategy())  # priority=10
        >>> strategy = registry.find_strategy(Path("test.xlsx"))
        >>> type(strategy).__name__
        'SpecificExcelStrategy'
    """
    
    def __init__(self):
        """
        Inicijalizuj registry sa praznom listom strategija.
        """
        self.strategies: List[ImportStrategy] = []
    
    def register(self, strategy: ImportStrategy) -> None:
        """
        Registruj novu strategiju.
        
        Strategije se automatski sortiraju po prioritetu (viši prvo).
        Ovo osigurava da specijalizovane strategije imaju prednost
        nad opštim strategijama.
        
        Args:
            strategy: ImportStrategy instanca za registraciju
        
        Primjer:
            >>> registry = StrategyRegistry()
            >>> registry.register(ExcelImportStrategy())
            >>> len(registry.strategies)
            1
        """
        self.strategies.append(strategy)
        # Sortiraj po prioritetu (viši prioritet = prvi u listi)
        self.strategies.sort(key=lambda s: s.priority, reverse=True)
    
    def find_strategy(self, filepath: Path) -> Optional[ImportStrategy]:
        """
        Pronađi odgovarajuću strategiju za dati fajl.
        
        Iterira kroz registrovane strategije (po prioritetu) i vraća
        prvu koja može procesirati dati fajl.
        
        Args:
            filepath: Putanja do fajla za koji se traži strategija
        
        Returns:
            ImportStrategy koja može procesirati fajl, ili None ako
            nijedna strategija ne podržava dati format.
        
        Primjer:
            >>> registry = StrategyRegistry()
            >>> registry.register(ExcelImportStrategy())
            >>> strategy = registry.find_strategy(Path("faktura.xlsx"))
            >>> strategy.strategy_name
            'Excel Importer'
        """
        for strategy in self.strategies:
            if strategy.can_handle(filepath):
                return strategy
        return None
    
    def import_file(
        self,
        filepath: Path,
        **kwargs: Any
    ) -> Any:
        """
        Importuj fajl koristeći odgovarajuću strategiju.
        
        Automatski pronalazi i koristi odgovarajuću strategiju za
        dati fajl. Prosljeđuje sve dodatne argumente strategiji.
        
        Args:
            filepath: Putanja do fajla za import
            **kwargs: Dodatni argumenti za strategiju (npr. progress_callback)
        
        Returns:
            Rezultat import-a (obično ImportResult ili List[InvoiceLine])
        
        Raises:
            FileNotSupportedError: Ako nijedna registrovana strategija
                                   ne može procesirati dati fajl.
        
        Primjer:
            >>> registry = get_registry()
            >>> result = registry.import_file(
            ...     Path("faktura.xlsx"),
            ...     progress_callback=lambda p: print(f"{p}%")
            ... )
        """
        strategy = self.find_strategy(filepath)
        
        if strategy is None:
            raise FileNotSupportedError(
                f"Nema registrovane strategije za format: {filepath.suffix or 'bez ekstenzije'}"
            )
        
        return strategy.import_file(filepath, **kwargs)
    
    def unregister(self, strategy_name: str) -> bool:
        """
        Ukloni strategiju po imenu.
        
        Args:
            strategy_name: Ime strategije za uklanjanje (strategy_name property)
        
        Returns:
            True ako je strategija uklonjena, False ako nije pronađena.
        
        Primjer:
            >>> registry.unregister("Excel Importer")
            True
        """
        for i, strategy in enumerate(self.strategies):
            if strategy.strategy_name == strategy_name:
                self.strategies.pop(i)
                return True
        return False
    
    def list_strategies(self) -> List[str]:
        """
        Vrati listu registrovanih strategija.
        
        Returns:
            Lista imena strategija (sortirane po prioritetu).
        
        Primjer:
            >>> registry.list_strategies()
            ['Specific Excel Importer', 'Excel Importer', 'PDF Importer']
        """
        return [s.strategy_name for s in self.strategies]
    
    def clear(self) -> None:
        """
        Ukloni sve registrovane strategije.
        
        Korisno za testing ili resetovanje registry-ja.
        """
        self.strategies.clear()


# ============================================================
# GLOBAL SINGLETON
# ============================================================

_registry: Optional[StrategyRegistry] = None


def get_registry() -> StrategyRegistry:
    """
    Dobij ili kreiraj global registry singleton.
    
    Prvi poziv kreira novi registry i automatski registruje
    default strategije. Svi naredni pozivi vraćaju istu instancu.
    
    Returns:
        StrategyRegistry: Global registry instanca
    
    Primjer:
        >>> registry1 = get_registry()
        >>> registry2 = get_registry()
        >>> registry1 is registry2
        True
    """
    global _registry
    
    if _registry is None:
        _registry = StrategyRegistry()
        _register_default_strategies(_registry)
    
    return _registry


def _register_default_strategies(registry: StrategyRegistry) -> None:
    """
    Registruj default strategije.
    
    Automatski registruje:
    - PDFImportStrategy (priority=10) - za PDF fakture
    - ExcelImportStrategy (priority=10) - za Excel fakture
    - XMLImportStrategy (priority=5) - za XML (ASYCUDA) deklaracije
    
    Strategije se registruju po prioritetu - specifične strategije
    (viši prioritet) se procjenjuju prije opštih.
    
    Args:
        registry: StrategyRegistry instanca za registraciju
    """
    from importers.strategies.pdf_strategy import PDFImportStrategy
    from importers.strategies.excel_strategy import ExcelImportStrategy
    from importers.strategies.xml_strategy import XMLImportStrategy
    
    # Registruj strategije (automatski se sortiraju po prioritetu)
    registry.register(PDFImportStrategy())      # priority=10
    registry.register(ExcelImportStrategy())    # priority=10
    registry.register(XMLImportStrategy())      # priority=5


def reset_registry() -> None:
    """
    Resetuj global registry (za testing).
    
    Uklanja global singleton i omogućava kreiranje novog.
    Korisno za unit testove gdje treba čist registry.
    
    Primjer:
        >>> reset_registry()
        >>> get_registry()  # Kreira novi registry
    """
    global _registry
    _registry = None
