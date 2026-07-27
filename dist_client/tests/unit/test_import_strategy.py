# tests/unit/test_import_strategy.py

"""
Unit Testovi za Import Strategy Sistem

Testiraju se:
- ImportStrategy abstract base class
- StrategyRegistry za upravljanje strategijama
- Custom exception hierarchy
"""

import pytest
from pathlib import Path

from importers.base_strategy import ImportStrategy
from importers.strategy_registry import (
    StrategyRegistry,
    get_registry,
    reset_registry
)
from importers.exceptions import (
    ImportError,
    FileNotSupportedError,
    ImportDetectionError,
    UnsupportedInvoiceFormatError,
    ParseError,
    ValidationError,
    PartialImportWarning
)


# ============================================================
# MOCK STRATEGY ZA TESTIRANJE
# ============================================================

class MockPDFStrategy(ImportStrategy):
    """
    Mock PDF strategija za testiranje.
    
    Implementira ImportStrategy interfejs za potrebe testova.
    """
    
    def can_handle(self, filepath: Path) -> bool:
        """PDF strategija handle-uje samo .pdf fajlove."""
        return filepath.suffix.lower() == ".pdf"
    
    def import_file(self, filepath, progress_callback=None):
        """Mock import - vraća praznu listu."""
        if progress_callback:
            progress_callback(100)
        return []
    
    @property
    def strategy_name(self) -> str:
        """Ime strategije."""
        return "Mock PDF"
    
    @property
    def priority(self) -> int:
        """Visok prioritet za PDF strategiju."""
        return 10


class MockExcelStrategy(ImportStrategy):
    """
    Mock Excel strategija za testiranje.
    
    Implementira ImportStrategy interfejs za potrebe testova.
    """
    
    def can_handle(self, filepath: Path) -> bool:
        """Excel strategija handle-uje .xlsx i .xls fajlove."""
        return filepath.suffix.lower() in [".xlsx", ".xls"]
    
    def import_file(self, filepath, progress_callback=None):
        """Mock import - vraća praznu listu."""
        if progress_callback:
            progress_callback(100)
        return []
    
    @property
    def strategy_name(self) -> str:
        """Ime strategije."""
        return "Mock Excel"
    
    @property
    def priority(self) -> int:
        """Niži prioritet od PDF."""
        return 5


class MockGenericStrategy(ImportStrategy):
    """
    Mock generička strategija za testiranje.
    
    Handle-uje sve fajlove (fallback strategija).
    """
    
    def can_handle(self, filepath: Path) -> bool:
        """Generic strategija handle-uje sve fajlove."""
        return True
    
    def import_file(self, filepath, progress_callback=None):
        """Mock import - vraća praznu listu."""
        return []
    
    @property
    def strategy_name(self) -> str:
        """Ime strategije."""
        return "Mock Generic"
    
    @property
    def priority(self) -> int:
        """Najniži prioritet (fallback)."""
        return 0


# ============================================================
# TEST: ImportStrategy Interface
# ============================================================

class TestImportStrategyInterface:
    """Testovi za ImportStrategy abstract base class."""
    
    def test_cannot_instantiate_abstract_class(self):
        """
        Test da ne može se instancirati direktno abstract klasa.
        
        ImportStrategy je ABC (Abstract Base Class) i ne može se
        instancirati direktno - mora se naslijediti.
        """
        with pytest.raises(TypeError):
            ImportStrategy()
    
    def test_abstract_methods_must_be_implemented(self):
        """
        Test da sve abstract metode moraju biti implementirane.
        
        Ako naslijediš ImportStrategy bez implementacije svih
        abstract metoda, Python će podići TypeError.
        """
        class IncompleteStrategy(ImportStrategy):
            def can_handle(self, filepath: Path) -> bool:
                return True
            # Nedostaje: import_file, strategy_name
        
        with pytest.raises(TypeError):
            IncompleteStrategy()


# ============================================================
# TEST: Mock Strategy Implementation
# ============================================================

class TestMockStrategyImplementation:
    """Testovi za mock strategije."""
    
    def test_mock_pdf_strategy_can_handle_pdf(self):
        """Test da MockPDFStrategy prepoznaje .pdf fajlove."""
        strategy = MockPDFStrategy()
        assert strategy.can_handle(Path("faktura.pdf")) is True
        assert strategy.can_handle(Path("FAKTURA.PDF")) is True
        assert strategy.can_handle(Path("faktura.pdf.gz")) is False
    
    def test_mock_pdf_strategy_cannot_handle_other_formats(self):
        """Test da MockPDFStrategy odbija druge formate."""
        strategy = MockPDFStrategy()
        assert strategy.can_handle(Path("faktura.xlsx")) is False
        assert strategy.can_handle(Path("faktura.xml")) is False
        assert strategy.can_handle(Path("faktura.txt")) is False
    
    def test_mock_pdf_strategy_import_file(self):
        """Test da MockPDFStrategy.import_file vraća listu."""
        strategy = MockPDFStrategy()
        result = strategy.import_file(Path("test.pdf"))
        assert isinstance(result, list)
        assert len(result) == 0
    
    def test_mock_pdf_strategy_import_with_progress(self):
        """Test da MockPDFStrategy poziva progress callback."""
        strategy = MockPDFStrategy()
        progress_values = []
        
        def callback(value):
            progress_values.append(value)
        
        strategy.import_file(Path("test.pdf"), progress_callback=callback)
        assert 100 in progress_values
    
    def test_mock_pdf_strategy_name(self):
        """Test da MockPDFStrategy ima ispravno ime."""
        strategy = MockPDFStrategy()
        assert strategy.strategy_name == "Mock PDF"
    
    def test_mock_pdf_strategy_priority(self):
        """Test da MockPDFStrategy ima visok prioritet."""
        strategy = MockPDFStrategy()
        assert strategy.priority == 10
    
    def test_mock_excel_strategy_can_handle_excel(self):
        """Test da MockExcelStrategy prepoznaje Excel fajlove."""
        strategy = MockExcelStrategy()
        assert strategy.can_handle(Path("faktura.xlsx")) is True
        assert strategy.can_handle(Path("faktura.xls")) is True
        assert strategy.can_handle(Path("faktura.XLSX")) is True
    
    def test_mock_generic_strategy_handles_all(self):
        """Test da MockGenericStrategy handle-uje sve fajlove."""
        strategy = MockGenericStrategy()
        assert strategy.can_handle(Path("anything.xyz")) is True
        assert strategy.can_handle(Path("no_extension")) is True
    
    def test_strategy_str_and_repr(self):
        """Test __str__ i __repr__ metode."""
        strategy = MockPDFStrategy()
        assert "Mock PDF" in str(strategy)
        assert "priority: 10" in str(strategy)
        assert "MockPDFStrategy" in repr(strategy)


# ============================================================
# TEST: StrategyRegistry
# ============================================================

class TestStrategyRegistry:
    """Testovi za StrategyRegistry klasu."""
    
    def setup_method(self):
        """Setup prije svakog testa - čist registry."""
        self.registry = StrategyRegistry()
    
    def test_registry_initialization(self):
        """Test da se registry inicijalizuje sa praznom listom."""
        assert len(self.registry.strategies) == 0
        assert self.registry.strategies == []
    
    def test_register_strategy(self):
        """Test dodavanje strategije u registry."""
        strategy = MockPDFStrategy()
        self.registry.register(strategy)
        
        assert len(self.registry.strategies) == 1
        assert self.registry.strategies[0] is strategy
    
    def test_strategies_sorted_by_priority(self):
        """Test da su strategije sortirane po prioritetu (viši prvo)."""
        # Registruj od najnižeg ka najvišem
        self.registry.register(MockGenericStrategy())  # priority=0
        self.registry.register(MockExcelStrategy())    # priority=5
        self.registry.register(MockPDFStrategy())      # priority=10
        
        # Provjeri da su sortirane obrnuto (najviši prioritet prvi)
        assert len(self.registry.strategies) == 3
        assert self.registry.strategies[0].strategy_name == "Mock PDF"
        assert self.registry.strategies[1].strategy_name == "Mock Excel"
        assert self.registry.strategies[2].strategy_name == "Mock Generic"
    
    def test_find_strategy_for_pdf(self):
        """Test pronalaženja strategije za PDF fajl."""
        self.registry.register(MockPDFStrategy())
        
        strategy = self.registry.find_strategy(Path("faktura.pdf"))
        
        assert strategy is not None
        assert strategy.strategy_name == "Mock PDF"
    
    def test_find_strategy_for_excel(self):
        """Test pronalaženja strategije za Excel fajl."""
        self.registry.register(MockExcelStrategy())
        
        strategy = self.registry.find_strategy(Path("faktura.xlsx"))
        
        assert strategy is not None
        assert strategy.strategy_name == "Mock Excel"
    
    def test_find_strategy_returns_none_for_unsupported(self):
        """Test da find_strategy vraća None za nepodržan format."""
        self.registry.register(MockPDFStrategy())
        
        strategy = self.registry.find_strategy(Path("faktura.xyz"))
        
        assert strategy is None
    
    def test_find_strategy_respects_priority(self):
        """Test da find_strategy vraća strategiju sa najvišim prioritetom."""
        # Registruj generic prvu (koja handle-uje sve)
        self.registry.register(MockGenericStrategy())
        # Registruj PDF drugu (specifičnija, viši prioritet)
        self.registry.register(MockPDFStrategy())
        
        # Za PDF fajl treba da se vrati PDF strategija (viši prioritet)
        strategy = self.registry.find_strategy(Path("faktura.pdf"))
        
        assert strategy is not None
        assert strategy.strategy_name == "Mock PDF"
    
    def test_import_file_with_strategy(self):
        """Test import_file sa odgovarajućom strategijom."""
        self.registry.register(MockPDFStrategy())
        
        result = self.registry.import_file(Path("test.pdf"))
        
        assert isinstance(result, list)
        assert len(result) == 0
    
    def test_import_file_raises_for_unsupported(self):
        """Test da import_file podiže FileNotSupportedError."""
        self.registry.register(MockPDFStrategy())
        
        with pytest.raises(FileNotSupportedError) as exc_info:
            self.registry.import_file(Path("unsupported.xyz"))
        
        assert "Nema registrovane strategije" in str(exc_info.value)
        assert ".xyz" in str(exc_info.value)
    
    def test_list_strategies(self):
        """Test listanje registrovanih strategija."""
        self.registry.register(MockPDFStrategy())
        self.registry.register(MockExcelStrategy())
        
        strategies = self.registry.list_strategies()
        
        assert len(strategies) == 2
        assert "Mock PDF" in strategies
        assert "Mock Excel" in strategies
    
    def test_unregister_strategy(self):
        """Test uklanjanja strategije."""
        strategy = MockPDFStrategy()
        self.registry.register(strategy)
        
        assert len(self.registry.strategies) == 1
        
        result = self.registry.unregister("Mock PDF")
        
        assert result is True
        assert len(self.registry.strategies) == 0
    
    def test_unregister_nonexistent_strategy(self):
        """Test uklanjanja nepostojeće strategije."""
        result = self.registry.unregister("Nonexistent")
        
        assert result is False
    
    def test_clear_registry(self):
        """Test brisanja svih strategija."""
        self.registry.register(MockPDFStrategy())
        self.registry.register(MockExcelStrategy())
        
        self.registry.clear()
        
        assert len(self.registry.strategies) == 0


# ============================================================
# TEST: Global Registry Singleton
# ============================================================

class TestGlobalRegistrySingleton:
    """Testovi za global registry singleton."""
    
    def teardown_method(self):
        """Cleanup nakon svakog testa - resetuj registry."""
        reset_registry()
    
    def test_get_registry_returns_singleton(self):
        """Test da get_registry vraća istu instancu."""
        reg1 = get_registry()
        reg2 = get_registry()
        
        assert reg1 is reg2
    
    def test_get_registry_creates_new_if_none(self):
        """Test da get_registry kreira novi registry ako ne postoji."""
        reset_registry()
        
        registry = get_registry()
        
        assert registry is not None
        assert isinstance(registry, StrategyRegistry)
    
    def test_get_registry_auto_registers_defaults(self):
        """Test da get_registry automatski registruje default strategije."""
        reset_registry()
        
        registry = get_registry()
        
        # _register_default_strategies je za sada prazna (TODO)
        # Kada se implementira, ovdje će biti provjera da su default
        # strategije registrovane
        assert isinstance(registry, StrategyRegistry)
    
    def test_reset_registry(self):
        """Test resetovanja global registry."""
        reg1 = get_registry()
        reset_registry()
        reg2 = get_registry()
        
        assert reg1 is not reg2


# ============================================================
# TEST: Custom Exceptions
# ============================================================

class TestCustomExceptions:
    """Testovi za custom exception hierarchy."""
    
    def test_import_error_is_exception(self):
        """Test da ImportError nasljeđuje Exception."""
        assert issubclass(ImportError, Exception)
    
    def test_file_not_supported_error_hierarchy(self):
        """Test hijerarhije FileNotSupportedError."""
        assert issubclass(FileNotSupportedError, ImportError)
        assert issubclass(FileNotSupportedError, Exception)
    
    def test_import_detection_error_hierarchy(self):
        """Test hijerarhije ImportDetectionError."""
        assert issubclass(ImportDetectionError, ImportError)
        assert issubclass(ImportDetectionError, Exception)
    
    def test_unsupported_invoice_format_error_hierarchy(self):
        """Test hijerarhije UnsupportedInvoiceFormatError."""
        assert issubclass(UnsupportedInvoiceFormatError, ImportError)
        assert issubclass(UnsupportedInvoiceFormatError, Exception)
    
    def test_parse_error_hierarchy(self):
        """Test hijerarhije ParseError."""
        assert issubclass(ParseError, ImportError)
        assert issubclass(ParseError, Exception)
    
    def test_validation_error_hierarchy(self):
        """Test hijerarhije ValidationError."""
        assert issubclass(ValidationError, ImportError)
        assert issubclass(ValidationError, Exception)
    
    def test_partial_import_warning_hierarchy(self):
        """Test hijerarhije PartialImportWarning."""
        assert issubclass(PartialImportWarning, Warning)
        # PartialImportWarning NE nasljeđuje ImportError
        assert not issubclass(PartialImportWarning, ImportError)
    
    def test_raising_file_not_supported(self):
        """Test podizanja FileNotSupportedError."""
        with pytest.raises(FileNotSupportedError) as exc_info:
            raise FileNotSupportedError("faktura.xyz")
        
        assert "faktura.xyz" in str(exc_info.value)
    
    def test_raising_parse_error(self):
        """Test podizanja ParseError."""
        with pytest.raises(ParseError) as exc_info:
            raise ParseError("Excel fajl je oštećen")
        
        assert "Excel fajl je oštećen" in str(exc_info.value)
    
    def test_raising_validation_error(self):
        """Test podizanja ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            raise ValidationError("JIB je obavezan", field="jib", value=None)
        
        assert "JIB je obavezan" in str(exc_info.value)
    
    def test_validation_error_has_field_attribute(self):
        """Test da ValidationError ima field atribut."""
        error = ValidationError("Greška", field="jib", value="123")
        
        assert error.field == "jib"
        assert error.value == "123"
        assert error.message == "Greška"
    
    def test_validation_error_str_with_field(self):
        """Test __str__ metode ValidationError sa field."""
        error = ValidationError("Greška", field="jib")
        
        assert "jib" in str(error)
    
    def test_validation_error_str_without_field(self):
        """Test __str__ metode ValidationError bez field."""
        error = ValidationError("Greška")
        
        assert str(error) == "Greška"
    
    def test_partial_import_warning_attributes(self):
        """Test da PartialImportWarning ima sve atribute."""
        warning = PartialImportWarning(
            imported_count=10,
            skipped_count=2,
            warnings=["Upozorenje 1"]
        )
        
        assert warning.imported_count == 10
        assert warning.skipped_count == 2
        assert len(warning.warnings) == 1
    
    def test_partial_import_warning_str(self):
        """Test __str__ metode PartialImportWarning."""
        warning = PartialImportWarning(
            imported_count=10,
            skipped_count=2
        )
        
        warning_str = str(warning)
        
        assert "Importovano: 10" in warning_str
        assert "Preskočeno: 2" in warning_str
    
    def test_catching_base_import_error(self):
        """Test hvatanja grešaka kroz base ImportError."""
        errors_caught = []
        
        try:
            raise FileNotSupportedError("test")
        except ImportError as e:
            errors_caught.append(type(e).__name__)
        
        try:
            raise ParseError("test")
        except ImportError as e:
            errors_caught.append(type(e).__name__)
        
        try:
            raise ValidationError("test")
        except ImportError as e:
            errors_caught.append(type(e).__name__)
        
        assert "FileNotSupportedError" in errors_caught
        assert "ParseError" in errors_caught
        assert "ValidationError" in errors_caught
    
    def test_catching_specific_error(self):
        """Test hvatanja specifične greške."""
        try:
            raise FileNotSupportedError("test")
        except FileNotSupportedError:
            pass  # Očekivano
        except ImportError:
            pytest.fail("Uhvaćen kao ImportError umjesto FileNotSupportedError")
