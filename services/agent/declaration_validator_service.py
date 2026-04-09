"""
Declaration Validator Service

Rule-based validacija kompletne deklaracije:
1. Zaglavlje (obavezna polja, sinhronizacija)
2. Naimenovanja (tarifni brojevi, konzistentnost)
3. Historijska analiza (supplier profiling)
4. Kontekstualne provjere (faktura analiza)
5. Pravne provjere (povlastice, dokumentacija)

Kombinuje sve postojeće servise za kompletnu analizu.
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class ValidationSeverity(Enum):
    """Nivo ozbiljnosti validacije."""
    ERROR = "error"      # Blokira export
    WARNING = "warning"  # Upozorenje, ne blokira
    INFO = "info"       # Informacija
    SUGGESTION = "suggestion"  # Preporuka


class ValidationCategory(Enum):
    """Kategorija validacije."""
    REQUIRED_FIELD = "required_field"
    SYNCHRONIZATION = "synchronization"
    CONSISTENCY = "consistency"
    HISTORICAL = "historical"
    LEGAL = "legal"
    CONTEXTUAL = "contextual"
    DOCUMENTATION = "documentation"


@dataclass
class ValidationItem:
    """Jedna validacijska stavka."""
    severity: ValidationSeverity
    category: ValidationCategory
    rule: str  # Rb. broj ili "general"
    field: str  # Naziv polja ili oblasti
    message: str  # Poruka za korisnika
    explanation: str = ""  # Detaljno objašnjenje
    fixable: bool = False  # Da li se može automatski popraviti
    fix_action: str = ""  # Akcija za popravku
    context: Dict[str, Any] = None  # Dodatni kontekst
    
    def __post_init__(self):
        if self.context is None:
            self.context = {}


@dataclass
class ValidationReport:
    """Kompletan izvještaj validacije."""
    valid: bool  # Da li je deklaracija validna za export
    error_count: int
    warning_count: int
    info_count: int
    suggestion_count: int
    
    # Grupisane stavke
    zaglavlje_items: List[ValidationItem]
    naimenovanja_items: List[ValidationItem]
    historical_items: List[ValidationItem]
    legal_items: List[ValidationItem]
    contextual_items: List[ValidationItem]
    
    # Sažetak
    summary: str = ""
    
    # Preporuke za popravke
    recommendations: List[str] = None
    
    def __post_init__(self):
        if self.recommendations is None:
            self.recommendations = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertuj u dict za prikaz u UI."""
        return {
            'valid': self.valid,
            'error_count': self.error_count,
            'warning_count': self.warning_count,
            'info_count': self.info_count,
            'suggestion_count': self.suggestion_count,
            'summary': self.summary,
            'recommendations': self.recommendations,
            'total_items': (
                len(self.zaglavlje_items) +
                len(self.naimenovanja_items) +
                len(self.historical_items) +
                len(self.legal_items) +
                len(self.contextual_items)
            )
        }


class DeclarationValidatorService:
    """
    Agent servis za inteligentnu validaciju kompletne deklaracije.
    
    Kombinuje:
    1. Postojeću validaciju (ZaglavljeService)
    2. Supplier profiling (SupplierProfilingService)
    3. Historijsko učenje (HistoricalLearningService)
    4. Enhanced tariff suggestions
    5. Kontekstualnu analizu
    """
    
    def __init__(self):
        """Inicijalizacija svih potrebnih servisa."""
        # Lazy loading servisa
        self._zaglavlje_service = None
        self._profiling_service = None
        self._historical_service = None
        self._enhanced_tariff_service = None
        
        # Cache za performance
        self.supplier_cache: Dict[str, Any] = {}
        
        print("✅ DeclarationValidatorService inicijalizovan")
    
    def validate_complete_declaration(
        self,
        zaglavlje_data: Dict[str, Any],
        naimenovanja_data: List[Dict[str, Any]],
        invoice_lines: List[Dict[str, Any]],
        draft: Any = None,
        import_attached_docs: List[Dict] = None
    ) -> ValidationReport:
        """
        Validiraj kompletnu deklaraciju sa agent analizom.
        
        Args:
            zaglavlje_data: Podaci zaglavlja
            naimenovanja_data: Lista naimenovanja
            invoice_lines: Stavke fakture
            draft: DeclarationDraft objekat (opciono)
            import_attached_docs: Importovani dokumenti (opciono)
        
        Returns:
            ValidationReport sa kompletnom analizom
        """
        print(f"🔍 Agent validacija: {len(naimenovanja_data)} naimenovanja, "
              f"{len(invoice_lines)} faktura stavki")
        
        all_items = []
        
        # 1. Osnovna validacija zaglavlja (postojeći sistem)
        zaglavlje_items = self._validate_zaglavlje(
            zaglavlje_data, draft, import_attached_docs
        )
        all_items.extend(zaglavlje_items)
        
        # 2. Validacija naimenovanja
        naimenovanja_items = self._validate_naimenovanja(
            naimenovanja_data, invoice_lines
        )
        all_items.extend(naimenovanja_items)
        
        # 3. Historijska analiza (ako imamo suppliera)
        supplier_name = zaglavlje_data.get('izvoznik_r1', '')
        if supplier_name:
            historical_items = self._validate_historical(
                supplier_name, naimenovanja_data, invoice_lines
            )
            all_items.extend(historical_items)
        else:
            historical_items = []
        
        # 4. Pravne provjere (povlastice, dokumentacija)
        legal_items = self._validate_legal(
            zaglavlje_data, naimenovanja_data, invoice_lines
        )
        all_items.extend(legal_items)
        
        # 5. Kontekstualne provjere
        contextual_items = self._validate_contextual(
            zaglavlje_data, naimenovanja_data, invoice_lines
        )
        all_items.extend(contextual_items)
        
        # 6. Izračunaj statistiku
        error_count = sum(1 for item in all_items if item.severity == ValidationSeverity.ERROR)
        warning_count = sum(1 for item in all_items if item.severity == ValidationSeverity.WARNING)
        info_count = sum(1 for item in all_items if item.severity == ValidationSeverity.INFO)
        suggestion_count = sum(1 for item in all_items if item.severity == ValidationSeverity.SUGGESTION)
        
        # 7. Generiši sažetak
        summary = self._generate_summary(
            error_count, warning_count, info_count, suggestion_count
        )
        
        # 8. Generiši preporuke
        recommendations = self._generate_recommendations(all_items)
        
        # 9. Kreiraj report
        report = ValidationReport(
            valid=error_count == 0,
            error_count=error_count,
            warning_count=warning_count,
            info_count=info_count,
            suggestion_count=suggestion_count,
            zaglavlje_items=[i for i in all_items if i.category in [
                ValidationCategory.REQUIRED_FIELD,
                ValidationCategory.SYNCHRONIZATION,
                ValidationCategory.CONSISTENCY
            ]],
            naimenovanja_items=[i for i in all_items if i.rule.startswith('Na')],
            historical_items=historical_items,
            legal_items=legal_items,
            contextual_items=contextual_items,
            summary=summary,
            recommendations=recommendations
        )
        
        print(f"✅ Agent validacija završena: {error_count} grešaka, "
              f"{warning_count} upozorenja")
        
        return report
    
    def _validate_zaglavlje(
        self,
        zaglavlje_data: Dict[str, Any],
        draft: Any,
        import_attached_docs: List[Dict]
    ) -> List[ValidationItem]:
        """Validiraj zaglavlje koristeći postojeći sistem."""
        items = []
        
        try:
            # Koristi postojeći ZaglavljeService
            from services.zaglavlje_service import ZaglavljeService
            
            service = ZaglavljeService()
            result = service.validate(zaglavlje_data, draft, import_attached_docs)
            
            # Konvertuj errors u ValidationItem
            for error in result.get('errors', []):
                items.append(ValidationItem(
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.REQUIRED_FIELD,
                    rule=error.get('rule', 'general'),
                    field=error.get('field', ''),
                    message=error.get('message', ''),
                    fixable=error.get('fixable', False),
                    fix_action=error.get('fix_action', '')
                ))
            
            # Konvertuj warnings
            for warning in result.get('warnings', []):
                items.append(ValidationItem(
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.CONSISTENCY,
                    rule=warning.get('rule', 'general'),
                    field=warning.get('field', ''),
                    message=warning.get('message', ''),
                    fixable=warning.get('fixable', False),
                    fix_action=warning.get('fix_action', '')
                ))
            
        except ImportError:
            print("⚠️ ZaglavljeService nije dostupan")
        except Exception as e:
            print(f"⚠️ Greška pri validaciji zaglavlja: {e}")
        
        return items
    
    def _validate_naimenovanja(
        self,
        naimenovanja_data: List[Dict[str, Any]],
        invoice_lines: List[Dict[str, Any]]
    ) -> List[ValidationItem]:
        """Validiraj naimenovanja."""
        items = []
        
        if not naimenovanja_data:
            items.append(ValidationItem(
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.REQUIRED_FIELD,
                rule="Naimenovanja",
                field="Broj stavki",
                message="Nema naimenovanja. Dodajte barem jednu stavku.",
                explanation="Deklaracija mora imati barem jedno naimenovanje."
            ))
            return items
        
        # Provjeri svako naimenovanje
        for i, item in enumerate(naimenovanja_data):
            item_num = i + 1
            
            # Obavezna polja
            if not item.get('tariff_code'):
                items.append(ValidationItem(
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.REQUIRED_FIELD,
                    rule=f"Na{item_num}",
                    field="Tarifni broj",
                    message=f"Stavka {item_num}: Tarifni broj je obavezan",
                    explanation="Svaka stavka mora imati tarifni broj."
                ))
            
            if not item.get('goods_trade_name'):
                items.append(ValidationItem(
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.REQUIRED_FIELD,
                    rule=f"Na{item_num}",
                    field="Naziv robe",
                    message=f"Stavka {item_num}: Naziv robe je obavezan",
                    explanation="Svaka stavka mora imati naziv robe."
                ))
            
            # Provjeri format tarifnog broja
            tariff = item.get('tariff_code', '')
            if tariff and not tariff.isdigit():
                items.append(ValidationItem(
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.CONSISTENCY,
                    rule=f"Na{item_num}",
                    field="Tarifni broj",
                    message=f"Stavka {item_num}: Tarifni broj '{tariff}' sadrži ne-digit karaktere",
                    explanation="Tarifni brojevi bi trebali sadržavati samo cifre."
                ))
            
            # Provjeri težine
            gross = item.get('gross_mass_kg', 0)
            net = item.get('net_mass_kg', 0)
            
            if gross and net and net > gross:
                items.append(ValidationItem(
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.CONSISTENCY,
                    rule=f"Na{item_num}",
                    field="Težine",
                    message=f"Stavka {item_num}: Neto težina ({net} kg) veća od bruto ({gross} kg)",
                    explanation="Neto težina ne može biti veća od bruto težine."
                ))
        
        # Provjeri duplikate (isti tarifni broj + zemlja + povlastica)
        self._check_duplicate_naimenovanja(naimenovanja_data, items)
        
        return items
    
    def _check_duplicate_naimenovanja(
        self,
        naimenovanja_data: List[Dict[str, Any]],
        items: List[ValidationItem]
    ):
        """Provjeri duplikate naimenovanja koje se mogu grupisati."""
        from collections import defaultdict
        
        # Grupiši po ključu za grupisanje
        groups = defaultdict(list)
        
        for i, item in enumerate(naimenovanja_data):
            key = (
                item.get('tariff_code', ''),
                item.get('origin_country_code', ''),
                item.get('preference_code', ''),
                item.get('goods_trade_name', '')[:50]  # Prvih 50 karaktera
            )
            groups[key].append(i + 1)  # +1 za human-readable broj
        
        # Pronađi grupe sa više od 1 stavke
        for key, indices in groups.items():
            if len(indices) > 1:
                tariff, country, preference, name = key
                
                if tariff:  # Samo ako imaju tarifni broj
                    items.append(ValidationItem(
                        severity=ValidationSeverity.SUGGESTION,
                        category=ValidationCategory.CONSISTENCY,
                        rule="Grupisanje",
                        field="Naimenovanja",
                        message=f"Stavke {', '.join(map(str, indices))} mogu se grupisati",
                        explanation=(
                            f"Sve stavke imaju isti tarifni broj ({tariff}), "
                            f"zemlju ({country}), povlasticu ({preference}). "
                            f"Razmotrite grupisanje radi jednostavnosti."
                        )
                    ))
    
    def _validate_historical(
        self,
        supplier_name: str,
        naimenovanja_data: List[Dict[str, Any]],
        invoice_lines: List[Dict[str, Any]]
    ) -> List[ValidationItem]:
        """Historijska analiza na osnovu supplier profiling."""
        items = []
        
        try:
            from services.agent.supplier_profiling_service import SupplierProfilingService
            
            service = SupplierProfilingService()
            profile = service.get_complete_profile(supplier_name)
            
            if not profile:
                # Nema historijskih podataka
                items.append(ValidationItem(
                    severity=ValidationSeverity.INFO,
                    category=ValidationCategory.HISTORICAL,
                    rule="Historija",
                    field="Supplier",
                    message=f"Nema historijskih podataka za {supplier_name}",
                    explanation="Ovo je prva deklaracija za ovog dobavljača ili nema historije u sistemu."
                ))
                return items
            
            # Supplier ima historiju
            items.append(ValidationItem(
                severity=ValidationSeverity.INFO,
                category=ValidationCategory.HISTORICAL,
                rule="Historija",
                field="Supplier",
                message=f"{supplier_name}: {profile.total_declarations} historijskih deklaracija",
                explanation=f"Supplier je ranije koristio sistem {profile.total_declarations} puta."
            ))
            
            # Analiziraj naimenovanja u odnosu na historiju
            for i, item in enumerate(naimenovanja_data):
                item_num = i + 1
                product_name = item.get('goods_trade_name', '')
                tariff_code = item.get('tariff_code', '')
                
                if not product_name or not tariff_code:
                    continue
                
                # Provjeri da li je proizvod nov za suppliera
                is_new = True
                for product_profile in profile.product_profiles.values():
                    similarity = self._calculate_similarity(
                        product_name,
                        product_profile.product_name
                    )
                    
                    if similarity > 0.7:  # Visoka sličnost
                        is_new = False
                        
                        # Provjeri da li je tarifni broj isti
                        if tariff_code != product_profile.tariff_code:
                            items.append(ValidationItem(
                                severity=ValidationSeverity.WARNING,
                                category=ValidationCategory.HISTORICAL,
                                rule=f"Na{item_num}",
                                field="Tarifni broj",
                                message=(
                                    f"Stavka {item_num}: Nov tarifni broj za poznat proizvod\n"
                                    f"Historijski: {product_profile.tariff_code}, Sada: {tariff_code}"
                                ),
                                explanation=(
                                    f"{supplier_name} je ranije koristio {product_profile.tariff_code} "
                                    f"za sličan proizvod '{product_profile.product_name[:50]}...'"
                                )
                            ))
                        break
                
                if is_new:
                    items.append(ValidationItem(
                        severity=ValidationSeverity.INFO,
                        category=ValidationCategory.HISTORICAL,
                        rule=f"Na{item_num}",
                        field="Proizvod",
                        message=f"Stavka {item_num}: Nov proizvod za {supplier_name}",
                        explanation=(
                            f"'{product_name[:50]}...' se prvi put pojavljuje kod ovog dobavljača. "
                            f"Provjeri tarifni broj."
                        )
                    ))
            
        except ImportError:
            print("⚠️ SupplierProfilingService nije dostupan")
        except Exception as e:
            print(f"⚠️ Greška pri historijskoj analizi: {e}")
        
        return items
    
    def _validate_legal(
        self,
        zaglavlje_data: Dict[str, Any],
        naimenovanja_data: List[Dict[str, Any]],
        invoice_lines: List[Dict[str, Any]]
    ) -> List[ValidationItem]:
        """Pravne provjere (povlastice, dokumentacija)."""
        items = []
        
        try:
            from services.agent.historical_learning_service_safe import HistoricalLearningServiceSafe
            
            service = HistoricalLearningServiceSafe()
            supplier_name = zaglavlje_data.get('izvoznik_r1', '')
            
            if not supplier_name:
                return items
            
            # Provjeri povlastice za svaku stavku
            for i, item in enumerate(naimenovanja_data):
                item_num = i + 1
                country = item.get('origin_country_code', '')
                preference = item.get('preference_code', '')
                
                if not country or not preference:
                    continue
                
                # Dobavi historijsku povlasticu
                historical_pref = service.get_preference_safe(supplier_name, country)
                
                if historical_pref and historical_pref != preference:
                    items.append(ValidationItem(
                        severity=ValidationSeverity.WARNING,
                        category=ValidationCategory.LEGAL,
                        rule=f"Na{item_num}",
                        field="Povlastica",
                        message=(
                            f"Stavka {item_num}: Povlastica se razlikuje od historijske\n"
                            f"Historijski: {historical_pref}, Sada: {preference}"
                        ),
                        explanation=(
                            f"{supplier_name} je ranije koristio {historical_pref} "
                            f"za {country}. Provjeri da li je {preference} tačna."
                        )
                    ))
                
                # Provjeri da li je povlastica validna za zemlju
                if country == "RS" and preference == "EUP":
                    items.append(ValidationItem(
                        severity=ValidationSeverity.ERROR,
                        category=ValidationCategory.LEGAL,
                        rule=f"Na{item_num}",
                        field="Povlastica",
                        message=f"Stavka {item_num}: EUP nije validna za Srbiju",
                        explanation="Srbija nije članica EU. EUP povlastica nije validna."
                    ))
                
                # Provjeri dokumentaciju za vrijednost preko 10.000 EUR
                item_value = float(item.get('item_value', 0) or 0)
                if item_value > 10000 and not preference:
                    items.append(ValidationItem(
                        severity=ValidationSeverity.WARNING,
                        category=ValidationCategory.DOCUMENTATION,
                        rule=f"Na{item_num}",
                        field="Dokumentacija",
                        message=f"Stavka {item_num}: Vrijednost preko 10.000 EUR bez povlastice",
                        explanation=(
                            "Za robu vrijednosti preko 10.000 EUR obično je potrebna "
                            "dodatna dokumentacija za povlasticu."
                        )
                    ))
            
        except ImportError:
            print("⚠️ HistoricalLearningService nije dostupan")
        except Exception as e:
            print(f"⚠️ Greška pri pravnim provjerama: {e}")
        
        return items
    
    def _validate_contextual(
        self,
        zaglavlje_data: Dict[str, Any],
        naimenovanja_data: List[Dict[str, Any]],
        invoice_lines: List[Dict[str, Any]]
    ) -> List[ValidationItem]:
        """Kontekstualne provjere (analiza fakture, kategorije)."""
        items = []
        
        try:
            # Analiziraj kategorije proizvoda
            categories = self._analyze_product_categories(naimenovanja_data)
            
            if len(categories) > 1:
                # Više kategorija u fakturi
                main_category = max(categories.items(), key=lambda x: x[1])[0]
                other_categories = [c for c in categories if c != main_category]
                
                if other_categories:
                    items.append(ValidationItem(
                        severity=ValidationSeverity.INFO,
                        category=ValidationCategory.CONTEXTUAL,
                        rule="Faktura",
                        field="Kategorije",
                        message=f"Faktura sadrži {len(categories)} različite kategorije",
                        explanation=(
                            f"Glavna kategorija: {main_category}. "
                            f"Ostale: {', '.join(other_categories)}. "
                            f"Provjeri da li svi proizvodi pripadaju istoj pošiljci."
                        )
                    ))
            
            # Provjeri konzistentnost sa dobavljačem
            supplier_name = zaglavlje_data.get('izvoznik_r1', '')
            if supplier_name:
                supplier_category = self._detect_supplier_category(supplier_name)
                
                if supplier_category and categories:
                    invoice_categories = set(categories.keys())
                    
                    if supplier_category not in invoice_categories:
                        items.append(ValidationItem(
                            severity=ValidationSeverity.WARNING,
                            category=ValidationCategory.CONTEXTUAL,
                            rule="Dobavljač",
                            field="Kategorija",
                            message=(
                                f"Dobavljač {supplier_name} uvozi {supplier_category}, "
                                f"ali faktura sadrži {', '.join(invoice_categories)}"
                            ),
                            explanation=(
                                f"Provjeri da li su proizvodi iz fakture konzistentni "
                                f"sa uobičajenim asortimanom dobavljača."
                            )
                        ))
            
            # Provjeri da li faktura ima origin statement
            has_origin_statement = self._check_origin_statement(invoice_lines)
            if has_origin_statement:
                items.append(ValidationItem(
                    severity=ValidationSeverity.INFO,
                    category=ValidationCategory.DOCUMENTATION,
                    rule="Faktura",
                    field="Izjava o poreklu",
                    message="Faktura sadrži izjavu o poreklu",
                    explanation="Detektovana izjava o poreklu na fakturi. Provjeri da li je potrebna dodatna dokumentacija."
                ))
            
        except Exception as e:
            print(f"⚠️ Greška pri kontekstualnim provjerama: {e}")
        
        return items
    
    def _analyze_product_categories(
        self,
        naimenovanja_data: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Analiziraj kategorije proizvoda u naimenovanjima."""
        categories = {}
        
        for item in naimenovanja_data:
            product_name = item.get('goods_trade_name', '')
            if product_name:
                category = self._detect_product_category(product_name)
                categories[category] = categories.get(category, 0) + 1
        
        return categories
    
    def _detect_product_category(self, product_name: str) -> str:
        """Detektuj kategoriju proizvoda."""
        product_lower = product_name.lower()
        
        if any(word in product_lower for word in ['alat', 'šraf', 'čekić', 'ključ']):
            return "ručni alati"
        elif any(word in product_lower for word in ['elektron', 'baterij', 'kabl', 'priključ']):
            return "elektronika"
        elif any(word in product_lower for word in ['keram', 'ploč', 'cigl', 'cigla']):
            return "keramički proizvodi"
        elif any(word in product_lower for word in ['tekstil', 'pamuk', 'pamuk', 'tkanin']):
            return "tekstil"
        elif any(word in product_lower for word in ['hrana', 'piće', 'vino', 'brašno']):
            return "hrana i pića"
        
        return "ostalo"
    
    def _detect_supplier_category(self, supplier_name: str) -> str:
        """Detektuj uobičajenu kategoriju dobavljača."""
        supplier_lower = supplier_name.lower()
        
        if any(word in supplier_lower for word in ['alat', 'tools', 'tool', 'alati']):
            return "ručni alati"
        elif any(word in supplier_lower for word in ['elektron', 'electronic', 'elektro']):
            return "elektronika"
        elif any(word in supplier_lower for word in ['keram', 'ceram', 'ploč', 'cigla']):
            return "keramički proizvodi"
        elif any(word in supplier_lower for word in ['tekstil', 'textil', 'pamuk', 'tkanin']):
            return "tekstil"
        elif any(word in supplier_lower for word in ['hrana', 'food', 'piće', 'drink']):
            return "hrana i pića"
        
        return ""
    
    def _check_origin_statement(self, invoice_lines: List[Dict[str, Any]]) -> bool:
        """Provjeri da li faktura sadrži izjavu o poreklu."""
        # Ovo je pojednostavljena provjera
        # U stvarnoj implementaciji bi se koristio OriginStatementDetector
        for line in invoice_lines:
            text = str(line).lower()
            if any(phrase in text for phrase in [
                'origin', 'porijeklo', 'poreklo', 'country of origin',
                'made in', 'proizvedeno u', 'izjava o poreklu'
            ]):
                return True
        return False
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Izračunaj sličnost između dva teksta."""
        if not text1 or not text2:
            return 0.0
        
        from difflib import SequenceMatcher
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    def _generate_summary(
        self,
        error_count: int,
        warning_count: int,
        info_count: int,
        suggestion_count: int
    ) -> str:
        """Generiši sažetak validacije."""
        parts = []
        
        if error_count > 0:
            parts.append(f"❌ {error_count} grešaka (blokiraju export)")
        
        if warning_count > 0:
            parts.append(f"⚠️ {warning_count} upozorenja")
        
        if info_count > 0:
            parts.append(f"ℹ️ {info_count} informacija")
        
        if suggestion_count > 0:
            parts.append(f"💡 {suggestion_count} preporuka")
        
        if not parts:
            return "✅ Validacija uspješna - nema grešaka"
        
        return ". ".join(parts)
    
    def _generate_recommendations(self, items: List[ValidationItem]) -> List[str]:
        """Generiši preporuke za popravke."""
        recommendations = []
        
        # Grupiši preporuke po prioritetu
        high_priority = [
            item for item in items 
            if item.severity == ValidationSeverity.ERROR
        ]
        
        medium_priority = [
            item for item in items 
            if item.severity == ValidationSeverity.WARNING
        ]
        
        # Dodaj preporuke za greške
        for item in high_priority[:3]:  # Maksimum 3
            recommendations.append(f"Popravi: {item.message}")
        
        # Dodaj preporuke za upozorenja
        for item in medium_priority[:2]:  # Maksimum 2
            recommendations.append(f"Provjeri: {item.message}")
        
        # Dodaj generalne preporuke ako nema grešaka
        if not high_priority and not medium_priority:
            recommendations.append("✅ Svi podaci su validni. Možete nastaviti sa exportom.")
        
        return recommendations
    
    def clear_cache(self):
        """Očisti cache."""
        self.supplier_cache.clear()
        print("🧹 Agent validation cache cleared")


# Helper funkcija za integraciju
def validate_declaration_with_agent(
    zaglavlje_data: Dict[str, Any],
    naimenovanja_data: List[Dict[str, Any]],
    invoice_lines: List[Dict[str, Any]],
    draft: Any = None
) -> ValidationReport:
    """
    Helper funkcija za validaciju deklaracije sa agentom.
    
    Args:
        zaglavlje_data: Podaci zaglavlja
        naimenovanja_data: Lista naimenovanja
        invoice_lines: Stavke fakture
        draft: DeclarationDraft (opciono)
    
    Returns:
        ValidationReport
    """
    service = DeclarationValidatorService()
    return service.validate_complete_declaration(
        zaglavlje_data=zaglavlje_data,
        naimenovanja_data=naimenovanja_data,
        invoice_lines=invoice_lines,
        draft=draft
    )


# Test funkcija
def test_agent_validation():
    """Testiraj agent validation servis."""
    print("🧪 Testiranje DeclarationValidatorService...")
    
    service = DeclarationValidatorService()
    
    # Test podaci
    zaglavlje_data = {
        'izvoznik_r1': 'MASTER TOOLS',
        'primalac_r1': 'COMPANY DOO',
        'deklarant_r1': 'DECLARANT DOO',
        'transport_id': 'BG-123-AB',
        'aktivno_transport': 'SRB-456-CD',
        'vid_25': '1',
        'uslovi_kod': 'CIF',
        'uslovi_mjesto': 'BEOGRAD',
        'valuta': 'EUR',
        'iznos': '18500.00',
    }
    
    naimenovanja_data = [
        {
            'tariff_code': '82052000',
            'goods_trade_name': 'Šrafciger profesionalni',
            'origin_country_code': 'DE',
            'preference_code': 'EUP',
            'gross_mass_kg': 5.0,
            'net_mass_kg': 4.5,
            'item_value': 1500.00
        },
        {
            'tariff_code': '85061000',
            'goods_trade_name': 'Baterija za alat',
            'origin_country_code': 'CN',
            'preference_code': '',
            'gross_mass_kg': 2.0,
            'net_mass_kg': 1.8,
            'item_value': 250.00
        },
        {
            'tariff_code': '82052000',  # Duplikat - može se grupisati
            'goods_trade_name': 'Čekić',
            'origin_country_code': 'DE',
            'preference_code': 'EUP',
            'gross_mass_kg': 3.0,
            'net_mass_kg': 2.8,
            'item_value': 800.00
        }
    ]
    
    invoice_lines = [
        {'naziv_robe': 'Šrafciger profesionalni', 'iznos': 1500.00, 'valuta': 'EUR'},
        {'naziv_robe': 'Baterija za alat', 'iznos': 250.00, 'valuta': 'EUR'},
        {'naziv_robe': 'Čekić', 'iznos': 800.00, 'valuta': 'EUR'},
    ]
    
    # Pokreni validaciju
    report = service.validate_complete_declaration(
        zaglavlje_data=zaglavlje_data,
        naimenovanja_data=naimenovanja_data,
        invoice_lines=invoice_lines
    )
    
    # Prikaži rezultate
    print(f"\n📊 REZULTAT VALIDACIJE:")
    print(f"   Valid: {report.valid}")
    print(f"   Greške: {report.error_count}")
    print(f"   Upozorenja: {report.warning_count}")
    print(f"   Informacije: {report.info_count}")
    print(f"   Preporuke: {report.suggestion_count}")
    print(f"   Sažetak: {report.summary}")
    
    # Prikaži preporuke
    if report.recommendations:
        print(f"\n🎯 PREPORUKE:")
        for i, rec in enumerate(report.recommendations, 1):
            print(f"   {i}. {rec}")
    
    # Prikaži po kategorijama
    print(f"\n📋 ZAGLAVLJE ({len(report.zaglavlje_items)} stavki):")
    for item in report.zaglavlje_items[:3]:  # Prve 3
        print(f"   {item.severity.value.upper()}: {item.message}")
    
    print(f"\n📦 NAIMENOVANJA ({len(report.naimenovanja_items)} stavki):")
    for item in report.naimenovanja_items[:3]:
        print(f"   {item.severity.value.upper()}: {item.message}")
    
    print(f"\n📊 HISTORIJSKA ANALIZA ({len(report.historical_items)} stavki):")
    for item in report.historical_items[:3]:
        print(f"   {item.severity.value.upper()}: {item.message}")
    
    print(f"\n⚖️  PRAVNE PROVJERE ({len(report.legal_items)} stavki):")
    for item in report.legal_items[:3]:
        print(f"   {item.severity.value.upper()}: {item.message}")
    
    print(f"\n🔍 KONTEKSTUALNE PROVJERE ({len(report.contextual_items)} stavki):")
    for item in report.contextual_items[:3]:
        print(f"   {item.severity.value.upper()}: {item.message}")
    
    print("\n✅ Agent validation testiran!")


if __name__ == "__main__":
    test_agent_validation()
