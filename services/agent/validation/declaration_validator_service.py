# SECTION: declaration-validator
# PURPOSE: Rule-based validacija kompletne deklaracije — greške, upozorenja, preporuke
# FIXES:
#   ce2ab0e — ordinal_no umjesto i+1 za prikaz Rb.X u upozorenjima
#   ef58456 — inspekcijsko upozorenje samo za can_auto_decide=True pravila
#   70d92e4 — _tariff_exists_in_db: 6-cifreni podbrojnik za ASYCUDA 8-cifrene kodove
# MEM: memory/2026-05-01_validator_ordinal_fix.md
# MEM: memory/2026-05-01_validator_inspection_tariff_fix.md

"""
Declaration Validator Service

Rule-based validacija kompletne deklaracije:
1. Zaglavlje (obavezna polja, sinhronizacija)
2. Naimenovanja (tarifni brojevi, konzistentnost)
3. Istorijska analiza (supplier profiling)
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
    ISTORIJA = "historical"
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
    3. Istorijsko učenje (HistoricalLearningService)
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
        
        # 3. Istorijska analiza (ako imamo suppliera)
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

        # 6. Provjera inspekcijskih dokumenata u Rb.44
        inspection_doc_items = self._validate_inspection_documents(
            naimenovanja_data, draft
        )
        all_items.extend(inspection_doc_items)
        contextual_items = contextual_items + inspection_doc_items
        
        # 7. Izračunaj statistiku
        error_count = sum(1 for item in all_items if item.severity == ValidationSeverity.ERROR)
        warning_count = sum(1 for item in all_items if item.severity == ValidationSeverity.WARNING)
        info_count = sum(1 for item in all_items if item.severity == ValidationSeverity.INFO)
        suggestion_count = sum(1 for item in all_items if item.severity == ValidationSeverity.SUGGESTION)
        
        # 8. Generiši sažetak
        summary = self._generate_summary(
            error_count, warning_count, info_count, suggestion_count
        )
        
        # 9. Generiši preporuke
        recommendations = self._generate_recommendations(all_items)
        
        # 10. Kreiraj report
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
            item_num = item.get("ordinal_no") or (i + 1)

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

            # Provjeri da li tarifni broj postoji u zvaničnoj tarifi
            if tariff and tariff.isdigit():
                if not self._tariff_exists_in_db(tariff):
                    items.append(ValidationItem(
                        severity=ValidationSeverity.ERROR,
                        category=ValidationCategory.CONSISTENCY,
                        rule=f"Na{item_num}",
                        field="Tarifni broj",
                        message=f"Stavka {item_num}: Tarifni broj '{tariff}' nije pronađen u zvaničnoj tarifi",
                        explanation=(
                            "Uneseni tarifni broj ne postoji u bazi zvanične carinske tarife. "
                            "Provjerite da li je broj tačan (ASYCUDA koristi 8 cifara)."
                        )
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
            groups[key].append(item.get("ordinal_no") or (i + 1))
        
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
        """Istorijska analiza na osnovu supplier profiling."""
        items = []
        
        try:
            from services.agent.learning.supplier_profiling_service import SupplierProfilingService
            
            service = SupplierProfilingService()
            profile = service.get_complete_profile(supplier_name)
            
            if not profile:
                # Nema istorijskih podataka
                items.append(ValidationItem(
                    severity=ValidationSeverity.INFO,
                    category=ValidationCategory.ISTORIJA,
                    rule="Istorija",
                    field="Supplier",
                    message=f"Nema istorijskih podataka za {supplier_name}",
                    explanation="Ovo je prva deklaracija za ovog dobavljača ili nema istorije u sistemu."
                ))
                return items
            
            # Supplier ima istoriju
            items.append(ValidationItem(
                severity=ValidationSeverity.INFO,
                category=ValidationCategory.ISTORIJA,
                rule="Istorija",
                field="Supplier",
                message=f"{supplier_name}: {profile.total_declarations} istorijskih deklaracija",
                explanation=f"Supplier je ranije koristio sistem {profile.total_declarations} puta."
            ))
            
            # Analiziraj naimenovanja u odnosu na istoriju —
            # javljamo SAMO ako je poznat proizvod dobio drugačiji tarifni broj
            for i, item in enumerate(naimenovanja_data):
                item_num = item.get("ordinal_no") or (i + 1)
                product_name = item.get('goods_trade_name', '')
                tariff_code = item.get('tariff_code', '')

                if not product_name or not tariff_code:
                    continue

                for product_profile in profile.product_profiles.values():
                    similarity = self._calculate_similarity(
                        product_name,
                        product_profile.product_name
                    )
                    if similarity > 0.7:
                        if tariff_code != product_profile.tariff_code:
                            items.append(ValidationItem(
                                severity=ValidationSeverity.WARNING,
                                category=ValidationCategory.ISTORIJA,
                                rule=f"Na{item_num}",
                                field="Tarifni broj",
                                message=(
                                    f"Stavka {item_num}: Promjena tarifnog broja — "
                                    f"istorijski {product_profile.tariff_code}, sada {tariff_code}"
                                ),
                                explanation=(
                                    f"{supplier_name} je ranije koristio {product_profile.tariff_code} "
                                    f"za '{product_profile.product_name[:60]}'. "
                                    f"Provjeri da li je promjena ispravna."
                                )
                            ))
                        break
            
        except ImportError:
            print("⚠️ SupplierProfilingService nije dostupan")
        except Exception as e:
            print(f"⚠️ Greška pri istorijskoj analizi: {e}")
        
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
            from services.agent.learning.historical_learning_service_safe import HistoricalLearningServiceSafe
            
            service = HistoricalLearningServiceSafe()
            supplier_name = zaglavlje_data.get('izvoznik_r1', '')
            
            if not supplier_name:
                return items
            
            # Provjeri povlastice za svaku stavku
            for i, item in enumerate(naimenovanja_data):
                item_num = item.get("ordinal_no") or (i + 1)
                country = item.get('origin_country_code', '')
                preference = item.get('preference_code', '')
                
                if not country or not preference:
                    continue
                
                # Dobavi istorijsku povlasticu
                historical_pref = service.get_preference_safe(supplier_name, country)
                
                if historical_pref and historical_pref != preference:
                    items.append(ValidationItem(
                        severity=ValidationSeverity.WARNING,
                        category=ValidationCategory.LEGAL,
                        rule=f"Na{item_num}",
                        field="Povlastica",
                        message=(
                            f"Stavka {item_num}: Povlastica se razlikuje od istorijske\n"
                            f"Istorijski: {historical_pref}, Sada: {preference}"
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
    
    def _tariff_exists_in_db(self, tariff_code: str) -> bool:
        """Provjeri da li tarifni broj postoji u tarifa_2026 (SQLite).

        ASYCUDA koristi 8-cifrene kodove (heading 4 + subheading 2 + nacionalni 2).
        Baza tarife ima 10-cifrene kodove. Prvih 6 cifara (heading + subheading)
        su pouzdane — provjera se radi na nivou 6-cifrenog podbroja.
        """
        try:
            from services.tarifa_service import trazi_po_kodu
            norm = tariff_code.strip().replace(" ", "").replace(".", "")
            if not norm:
                return True

            # Pokušaj exact match
            if trazi_po_kodu(norm):
                return True

            # Za 8-cifrene ASYCUDA kodove: provjeri 6-cifreni podbrojnik (heading+subheading)
            if len(norm) == 8:
                return bool(trazi_po_kodu(norm[:6]))

            return False
        except Exception as e:
            print(f"⚠️ Greška pri provjeri tarife {tariff_code}: {e}")
            return True  # U slučaju greške ne blokiramo

    # Mapiranje tipa inspekcije na šifru dokumenta u priloženim dokumentima zaglavlja
    _INSPECTION_DOC_MAP: dict[str, tuple[str, list[str]]] = {
        #                    primarni   alternativne šifre
        "sanitary":         ("N852", []),   # Inspekcija za hranu
        "veterinary":       ("N853", []),   # Veterinarska inspekcija
        "phytosanitary":    ("N851", []),   # Fitosanitarna inspekcija
        "quality_control":  ("N003", []),   # Zdravstvena inspekcija
        "market_inspection": ("N003", []),  # Tržna inspekcija (nema posebnog koda, koristi N003)
        "medicines_agency": ("AGL",  []),   # Agencija za lijekove
    }

    def _validate_inspection_documents(
        self,
        naimenovanja_data: List[Dict[str, Any]],
        draft: Any
    ) -> List[ValidationItem]:
        """
        Provjeri da li su inspekcijska uvjerenja priložena u Rb.44
        za stavke koje zahtijevaju inspekciju.
        """
        items = []
        if not draft:
            return items

        try:
            from services.inspection_service import get_inspection_service

            svc = get_inspection_service()

            # Skup šifri dokumenata koji su priloženi u Rb.44
            attached_codes = {
                doc.code.strip().upper()
                for doc in getattr(draft, "header_attached_documents", [])
                if doc.code
            }

            # Za svaki tip inspekcije pamtimo koje stavke ga zahtijevaju
            # da bismo dali jedno objedinjeno upozorenje po tipu, ne po stavci
            missing: dict[str, list[int]] = {}

            for i, item in enumerate(naimenovanja_data):
                tariff = item.get("tariff_code", "")
                if not tariff:
                    continue

                result = svc.check(tariff)
                if not result.requires_any_inspection:
                    continue

                rb_x = item.get("ordinal_no") or (i + 1)
                for match in result.matches:
                    # Samo can_auto_decide=True trigguje obavezno upozorenje.
                    # can_auto_decide=False znači sistem ne može sam utvrditi — preskačemo.
                    if not match.can_auto_decide:
                        continue
                    itype = match.inspection_type
                    entry = self._INSPECTION_DOC_MAP.get(itype)
                    if not entry:
                        continue
                    primary, alternatives = entry
                    all_accepted = {primary.upper()} | {a.upper() for a in alternatives}
                    if not all_accepted & attached_codes:
                        missing.setdefault(itype, []).append(rb_x)

            from services.inspection_service import INSPECTION_LABELS
            for itype, stavke in missing.items():
                primary, alternatives = self._INSPECTION_DOC_MAP[itype]
                label = INSPECTION_LABELS.get(itype, itype)
                alt_str = f" (ili {', '.join(alternatives)})" if alternatives else ""
                items.append(ValidationItem(
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.DOCUMENTATION,
                    rule="Inspekcija",
                    field="Priloženi dokumenti u zaglavlju",
                    message=(
                        f"{label}: dokument '{primary}'{alt_str} nije priložen "
                        f"(stavke: {', '.join(map(str, stavke))})"
                    ),
                    explanation=(
                        f"Stavke {', '.join(map(str, stavke))} imaju tarifne brojeve koji "
                        f"zahtijevaju {label.lower()}. Dodajte dokument šifre '{primary}' "
                        f"u priložene dokumente u zaglavlju."
                    )
                ))

        except Exception as e:
            print(f"⚠️ Greška pri provjeri inspekcijskih dokumenata: {e}")

        return items

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
    
    print(f"\n📊 ISTORIJSKA ANALIZA ({len(report.historical_items)} stavki):")
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


# ---------------------------------------------------------------------------
# Backward compat: ComplianceCheckService (premješteno iz compliance_check_service.py)
# ---------------------------------------------------------------------------

import logging as _logging
import difflib as _difflib
from dataclasses import dataclass as _dataclass, field as _field
from typing import Literal as _Literal, List as _List

_compliance_logger = _logging.getLogger("deklarant_pro.compliance_check")


@_dataclass
class Issue:
    severity: _Literal['error', 'warning', 'info']
    code: str
    message: str
    item_index: int = -1


@_dataclass
class ComplianceResult:
    issues: _List[Issue] = _field(default_factory=list)

    @property
    def errors(self):
        return [i for i in self.issues if i.severity == 'error']

    @property
    def warnings(self):
        return [i for i in self.issues if i.severity == 'warning']

    @property
    def is_ok(self) -> bool:
        return len(self.errors) == 0

    def summary_html(self) -> str:
        if not self.issues:
            return "✅ <b>Deklaracija je kompletna</b> — nisu pronađeni problemi."
        lines = []
        if self.errors:
            lines.append(f"<b style='color:#b05050;'>❌ Greške ({len(self.errors)}):</b>")
            for iss in self.errors:
                loc = f" [stavka {iss.item_index}]" if iss.item_index >= 0 else ""
                lines.append(f"&nbsp;&nbsp;• {iss.message}{loc}")
        if self.warnings:
            lines.append(f"<b style='color:#b8963a;'>⚠️ Upozorenja ({len(self.warnings)}):</b>")
            for iss in self.warnings:
                loc = f" [stavka {iss.item_index}]" if iss.item_index >= 0 else ""
                lines.append(f"&nbsp;&nbsp;• {iss.message}{loc}")
        info_issues = [i for i in self.issues if i.severity == 'info']
        if info_issues:
            lines.append(f"<b style='color:#4a7890;'>ℹ️ Napomene ({len(info_issues)}):</b>")
            for iss in info_issues:
                lines.append(f"&nbsp;&nbsp;• {iss.message}")
        return "<br>".join(lines)


class ComplianceCheckService:
    """
    Provjerava kompletnost i konzistentnost stavki fakture/deklaracije.

    Upotreba:
        svc = ComplianceCheckService()
        result = svc.check(draft)
        html = result.summary_html()
    """

    def check(self, draft) -> ComplianceResult:
        result = ComplianceResult()
        lines = getattr(draft, 'invoice_lines', []) or []
        if not lines:
            result.issues.append(Issue('warning', 'empty', "Nema uvezenih stavki fakture."))
            return result
        self._check_tariff_codes(lines, result)
        self._check_zemlja_porijekla(lines, result)
        self._check_tezine(draft, lines, result)
        self._check_eur1_povlastica(lines, result)
        self._check_naimenovanja(draft, result)
        self._check_izvoznik_uvoznik(draft, lines, result)
        self._check_attached_docs(draft, result)
        return result

    def _check_tariff_codes(self, lines, result: ComplianceResult):
        bez_tarife = [i for i, l in enumerate(lines, 1) if not getattr(l, 'tarifni_broj', None)]
        if bez_tarife:
            indices = ", ".join(str(i) for i in bez_tarife[:5])
            msg = f"Stavke bez tarifnog broja: {indices}" if len(bez_tarife) <= 5 else f"{len(bez_tarife)} stavki nema tarifni broj."
            result.issues.append(Issue('error', 'no_tariff', msg))
        try:
            from services.tarifa_service import trazi_po_kodu
            seen = set()
            for i, l in enumerate(lines, 1):
                kod = (getattr(l, 'tarifni_broj', '') or '').strip()
                if kod and kod not in seen:
                    seen.add(kod)
                    if not trazi_po_kodu(kod):
                        result.issues.append(Issue('error', 'invalid_tariff',
                            f"Tarifni broj '{kod}' nije pronađen u Carinskoj tarifi 2026.", item_index=i))
        except Exception as e:
            _compliance_logger.warning("Greška pri provjeri tarife: %s", e)

    def _check_zemlja_porijekla(self, lines, result: ComplianceResult):
        bez_zemlje = [i for i, l in enumerate(lines, 1) if not getattr(l, 'zemlja_porijekla', None)]
        if bez_zemlje:
            indices = ", ".join(str(i) for i in bez_zemlje[:5])
            msg = f"Stavke bez zemlje porijekla: {indices}" if len(bez_zemlje) <= 5 else f"{len(bez_zemlje)} stavki nema zemlju porijekla."
            result.issues.append(Issue('error', 'no_country', msg))

    def _check_tezine(self, draft, lines, result: ComplianceResult):
        ukupno_bruto = sum(getattr(l, 'bruto_kg', 0) or 0 for l in lines)
        ukupno_neto = sum(getattr(l, 'neto_kg', 0) or 0 for l in lines)
        if ukupno_bruto <= 0:
            result.issues.append(Issue('warning', 'no_weight', "Ukupna bruto težina je 0 — provjeri da li su težine učitane."))
        elif ukupno_neto > ukupno_bruto:
            result.issues.append(Issue('warning', 'weight_inconsistent',
                f"Neto ({ukupno_neto:.3f} kg) je veći od bruto ({ukupno_bruto:.3f} kg)."))
        elif ukupno_neto <= 0:
            result.issues.append(Issue('info', 'no_neto', "Neto težina je 0 — biće jednaka bruto pri kreiranju naimenovanja."))
        # Poređenje faktura vs naimenovanja težina
        items = getattr(draft, 'items', []) or []
        if items:
            naim_bruto = sum(getattr(it, 'gross_mass_kg', 0) or 0 for it in items)
            naim_neto = sum(getattr(it, 'net_mass_kg', 0) or 0 for it in items)
            if naim_bruto > 0 and ukupno_bruto > 0:
                razlika_bruto = abs(naim_bruto - ukupno_bruto) / ukupno_bruto
                if razlika_bruto > 0.05:
                    result.issues.append(Issue('warning', 'weight_naim_mismatch',
                        f"Bruto težina fakture ({ukupno_bruto:.3f} kg) i naimenovanja ({naim_bruto:.3f} kg) se razlikuju za >{razlika_bruto*100:.0f}%."))

    def _check_eur1_povlastica(self, lines, result: ComplianceResult):
        needs_doc = [i for i, l in enumerate(lines, 1)
                     if getattr(l, 'povlastica', None)
                     and not getattr(l, 'has_origin_statement', False)
                     and not getattr(l, 'eur1_number', None)]
        if needs_doc:
            indices = ", ".join(str(i) for i in needs_doc[:5])
            msg = f"Stavke sa povlasticom ali bez EUR.1/izjave: {indices}" if len(needs_doc) <= 5 else f"{len(needs_doc)} stavki ima povlasticu ali nema EUR.1 ni izjavu o porijeklu."
            result.issues.append(Issue('warning', 'no_eur1', msg))

    def _check_naimenovanja(self, draft, result: ComplianceResult):
        items = getattr(draft, 'items', []) or []
        if not items:
            return
        bez_tarife_naim = [i for i, it in enumerate(items, 1) if not getattr(it, 'tariff_code', None)]
        if bez_tarife_naim:
            result.issues.append(Issue('error', 'naim_no_tariff', f"{len(bez_tarife_naim)} naimenovanja bez tarifnog broja."))
        bez_procedure = [i for i, it in enumerate(items, 1) if not getattr(it, 'procedure_code', None)]
        if bez_procedure:
            result.issues.append(Issue('warning', 'naim_no_procedure', f"{len(bez_procedure)} naimenovanja bez šifre postupka (Rub.37)."))

    @staticmethod
    def _fuzzy_match(a: str, b: str) -> float:
        """Vraća sličnost dva string-a [0.0-1.0] (case-insensitive)."""
        a, b = (a or "").lower().strip(), (b or "").lower().strip()
        if not a or not b:
            return 0.0
        return _difflib.SequenceMatcher(None, a, b).ratio()

    def _check_izvoznik_uvoznik(self, draft, lines, result: ComplianceResult):
        izvoznik_zag = (getattr(draft, 'izvoznik_naziv', '') or '').strip()
        primalac_zag = (getattr(draft, 'primalac_naziv', '') or '').strip()

        # Skupljamo jedinstvene vrijednosti izvoznika/uvoznika iz fakture
        faktura_izvoznici = list({
            (getattr(l, 'exporter', None) and getattr(l.exporter, 'name', '')) or ''
            for l in lines
        } - {''})
        faktura_uvoznici = list({
            (getattr(l, 'importer', None) and getattr(l.importer, 'name', '')) or ''
            for l in lines
        } - {''})

        THRESHOLD = 0.55  # dopušta razlike u skraćenicama (d.o.o. vs doo, Ltd vs Limited)

        if izvoznik_zag and faktura_izvoznici:
            best = max(self._fuzzy_match(izvoznik_zag, fn) for fn in faktura_izvoznici)
            if best < THRESHOLD:
                result.issues.append(Issue('warning', 'izvoznik_mismatch',
                    f"Izvoznik u Zaglavlju ('{izvoznik_zag}') ne odgovara fakturi "
                    f"('{faktura_izvoznici[0]}'). Provjeri Rubriku 2."))
            elif best < 0.85:
                result.issues.append(Issue('info', 'izvoznik_partial',
                    f"Izvoznik — djelimično podudaranje: Zaglavlje='{izvoznik_zag}', "
                    f"Faktura='{faktura_izvoznici[0]}'."))
        elif izvoznik_zag and not faktura_izvoznici:
            result.issues.append(Issue('info', 'no_faktura_izvoznik',
                "Faktura ne sadrži podatke o izvozniku — provjeri ručno (Rubrika 2)."))
        elif not izvoznik_zag and faktura_izvoznici:
            result.issues.append(Issue('warning', 'no_zag_izvoznik',
                f"Zaglavlje nema izvoznika — faktura navodi '{faktura_izvoznici[0]}'. "
                "Unesi podatke u Rubriku 2."))

        if primalac_zag and faktura_uvoznici:
            best = max(self._fuzzy_match(primalac_zag, fu) for fu in faktura_uvoznici)
            if best < THRESHOLD:
                result.issues.append(Issue('warning', 'primalac_mismatch',
                    f"Primalac u Zaglavlju ('{primalac_zag}') ne odgovara fakturi "
                    f"('{faktura_uvoznici[0]}'). Provjeri Rubriku 8."))
            elif best < 0.85:
                result.issues.append(Issue('info', 'primalac_partial',
                    f"Primalac — djelimično podudaranje: Zaglavlje='{primalac_zag}', "
                    f"Faktura='{faktura_uvoznici[0]}'."))
        elif not primalac_zag and faktura_uvoznici:
            result.issues.append(Issue('warning', 'no_zag_primalac',
                f"Zaglavlje nema primaoca — faktura navodi '{faktura_uvoznici[0]}'. "
                "Unesi podatke u Rubriku 8."))

    def _check_attached_docs(self, draft, result: ComplianceResult):
        header_docs = getattr(draft, 'header_attached_documents', []) or []
        items = getattr(draft, 'items', []) or []

        # Skupi sve dokumente sa stavki naimenovanja
        item_doc_strings = []
        for it in items:
            for field_name in ('attached_document1', 'attached_document2',
                               'attached_document3', 'attached_document4', 'attached_document5'):
                val = (getattr(it, field_name, '') or '').strip()
                if val:
                    item_doc_strings.append(val)
            for ad in (getattr(it, 'attached_documents', []) or []):
                code = (getattr(ad, 'document_code', '') or '').strip()
                if code:
                    item_doc_strings.append(code)

        ukupno_docs = len(header_docs) + len(item_doc_strings)

        if ukupno_docs == 0:
            result.issues.append(Issue('warning', 'no_docs',
                "Nije priložen nijedan dokument (Rubrika 44). Provjeri CMR, fakturu, EUR.1."))
            return

        # Provjera: ima li stavki sa povlasticom ali bez EUR.1 u Rub.44
        lines = getattr(draft, 'invoice_lines', []) or []
        stavke_sa_povlasticom = [l for l in lines if getattr(l, 'povlastica', None)]
        if stavke_sa_povlasticom:
            sve_kodovi = " ".join(item_doc_strings)
            header_kodovi = " ".join(
                (getattr(d, 'document_code', '') or '') for d in header_docs
            )
            eur1_prisutan = any(
                k in sve_kodovi.upper() or k in header_kodovi.upper()
                for k in ('EUR', 'N864', 'N865', 'C019', 'U001')
            )
            if not eur1_prisutan:
                result.issues.append(Issue('warning', 'no_eur1_doc',
                    f"{len(stavke_sa_povlasticom)} stavki ima povlasticu, ali EUR.1 / "
                    "izjava o porijeklu nije pronađena u Rub.44."))

        result.issues.append(Issue('info', 'docs_ok',
            f"Rubrika 44: {ukupno_docs} dokument(a) priloženo."))
