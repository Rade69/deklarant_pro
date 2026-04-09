"""
Enhanced Tariff Suggestion Service

Kombinuje postojeći HybridTariffAgent sa:
1. Historijskim podacima o dobavljaču
2. Kontekstualnim informacijama
3. Supplier profiling
4. Warnings i objašnjenja
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from services.agent.hybrid_tariff_agent import HybridTariffAgent
from services.agent.historical_learning_service_safe import HistoricalLearningServiceSafe
from services.agent.supplier_profiling_service import SupplierProfilingService
from services.agent.hybrid_matching_service import HybridMatchingService
from gui.dialogs.enhanced_tariff_suggestion_dialog import (
    DialogContext,
    create_context_from_invoice
)


@dataclass
class EnhancedSuggestionResult:
    """Rezultat enhanced suggestion servisa."""
    selected_tariff: str
    basic_suggestions: List[Dict[str, Any]]
    agent_suggestions: List[Dict[str, Any]]
    context: DialogContext
    explanation: str = ""


class EnhancedTariffSuggestionService:
    """
    Enhanced servis za sugestije tarifnih brojeva.
    
    Kombinuje:
    1. Postojeći HybridTariffAgent
    2. Historijske podatke
    3. Supplier profiling
    4. Kontekstualne informacije
    """
    
    def __init__(self):
        """Inicijalizacija svih servisa."""
        self.hybrid_agent = HybridTariffAgent()
        self.historical_service = HistoricalLearningServiceSafe()
        self.profiling_service = SupplierProfilingService()
        self.hybrid_matching = HybridMatchingService()
        
        # Cache za brži pristup
        self.supplier_cache: Dict[str, Any] = {}
    
    def suggest_with_context(
        self,
        product_name: str,
        supplier_name: str = "",
        origin_country: str = "",
        invoice_lines: List[Dict] = None,
        use_enhanced_dialog: bool = True
    ) -> Optional[EnhancedSuggestionResult]:
        """
        Sugeriši tarifni broj sa kontekstualnim informacijama.
        
        Args:
            product_name: Naziv proizvoda
            supplier_name: Ime dobavljača (opciono)
            origin_country: Zemlja porijekla (opciono)
            invoice_lines: Lista stavki fakture za kontekst (opciono)
            use_enhanced_dialog: Da li koristiti enhanced dijalog
        
        Returns:
            EnhancedSuggestionResult ili None
        """
        # 1. Dobavi osnovne prijedloge (postojeći sistem)
        basic_suggestions = self._get_basic_suggestions(
            product_name, 
            origin_country
        )
        
        # 2. Dobavi agent prijedloge (historija + kontekst)
        agent_suggestions = self._get_agent_suggestions(
            product_name,
            supplier_name,
            origin_country,
            invoice_lines
        )
        
        # 3. Kreiraj kontekst za dijalog
        context = create_context_from_invoice(
            product_name=product_name,
            supplier_name=supplier_name,
            invoice_lines=invoice_lines or []
        )
        
        # 4. Ako ne koristimo enhanced dijalog, vrati najbolji prijedlog
        if not use_enhanced_dialog:
            return self._get_best_suggestion(
                basic_suggestions,
                agent_suggestions,
                context
            )
        
        # 5. Inače, vrati podatke za enhanced dijalog
        return EnhancedSuggestionResult(
            selected_tariff="",
            basic_suggestions=basic_suggestions,
            agent_suggestions=agent_suggestions,
            context=context
        )
    
    def _get_basic_suggestions(
        self,
        product_name: str,
        origin_country: str = ""
    ) -> List[Dict[str, Any]]:
        """Dobavi osnovne prijedloge iz HybridTariffAgent."""
        try:
            # Koristi HybridTariffAgent
            result = self.hybrid_agent.decide_tariff(
                naziv_robe=product_name,
                zemlja_porijekla=origin_country
            )
            
            suggestions = []
            
            # Dodaj glavni prijedlog
            if result.get('tarifni_broj'):
                suggestions.append({
                    'tariff_code': result['tarifni_broj'],
                    'description': result.get('explanation', ''),
                    'similarity': result.get('confidence', 0.5),
                    'method': result.get('method', 'ai'),
                    'explanation': self._format_explanation(result),
                    'needs_review': result.get('needs_review', True)
                })
            
            # Dodaj kandidate
            for candidate in result.get('candidates', [])[:3]:
                if candidate.get('tarifni_broj'):
                    suggestions.append({
                        'tariff_code': candidate['tarifni_broj'],
                        'description': candidate.get('naziv_robe', ''),
                        'similarity': candidate.get('confidence', 0.5),
                        'method': candidate.get('source', 'candidate'),
                        'explanation': f"Alternativni prijedlog iz {candidate.get('source', 'rag')}",
                        'needs_review': True
                    })
            
            return suggestions
            
        except Exception as e:
            print(f"⚠️ Greška pri dobavljanju basic suggestions: {e}")
            return []
    
    def _get_agent_suggestions(
        self,
        product_name: str,
        supplier_name: str,
        origin_country: str,
        invoice_lines: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Dobavi agent prijedloge (historija + kontekst)."""
        suggestions = []
        
        # 1. Historijski prijedlozi
        historical_suggestions = self._get_historical_suggestions(
            product_name,
            supplier_name,
            origin_country
        )
        suggestions.extend(historical_suggestions)
        
        # 2. Hybrid matching prijedlozi
        hybrid_suggestions = self._get_hybrid_matching_suggestions(
            product_name,
            supplier_name,
            origin_country
        )
        suggestions.extend(hybrid_suggestions)
        
        # 3. Kontekstualni prijedlozi (analiza fakture)
        contextual_suggestions = self._get_contextual_suggestions(
            product_name,
            supplier_name,
            invoice_lines
        )
        suggestions.extend(contextual_suggestions)
        
        return suggestions
    
    def _get_historical_suggestions(
        self,
        product_name: str,
        supplier_name: str,
        origin_country: str
    ) -> List[Dict[str, Any]]:
        """Dobavi historijske prijedloge za dobavljača."""
        if not supplier_name:
            return []
        
        suggestions = []
        
        try:
            # Provjeri historijske podatke
            profile = self.profiling_service.get_complete_profile(supplier_name)
            
            if profile and profile.product_profiles:
                # Pronađi slične proizvode u historiji
                for product_profile in profile.product_profiles.values():
                    similarity = self._calculate_similarity(
                        product_name,
                        product_profile.product_name
                    )
                    
                    if similarity > 0.6:  # Prilična sličnost
                        suggestions.append({
                            'tariff_code': product_profile.tariff_code,
                            'description': product_profile.product_name,
                            'confidence': similarity * product_profile.confidence,
                            'source': 'historical',
                            'explanation': (
                                f"{supplier_name} ranije koristio ovaj tarifni broj "
                                f"({product_profile.usage_count} puta) za sličan proizvod"
                            ),
                            'needs_review': similarity < 0.8
                        })
            
        except Exception as e:
            print(f"⚠️ Greška pri dobavljanju historijskih suggestions: {e}")
        
        return suggestions
    
    def _get_hybrid_matching_suggestions(
        self,
        product_name: str,
        supplier_name: str,
        origin_country: str
    ) -> List[Dict[str, Any]]:
        """Dobavi hybrid matching prijedloge."""
        suggestions = []
        
        try:
            # Koristi HybridMatchingService
            match_result = self.hybrid_matching.find_hybrid_mapping(
                product_code='',
                naziv_robe=product_name,
                supplier=supplier_name,
                country=origin_country,
                min_confidence=0.50
            )
            
            if match_result and match_result.tariff_mapping:
                suggestions.append({
                    'tariff_code': match_result.tariff_mapping.tarifni_broj,
                    'description': match_result.tariff_mapping.naziv_robe,
                    'confidence': match_result.confidence,
                    'source': 'hybrid_matching',
                    'explanation': (
                        f"Hybrid matching: {match_result.method} "
                        f"({match_result.explanation})"
                    ),
                    'needs_review': match_result.confidence < 0.70
                })
            
        except Exception as e:
            print(f"⚠️ Greška pri hybrid matching: {e}")
        
        return suggestions
    
    def _get_contextual_suggestions(
        self,
        product_name: str,
        supplier_name: str,
        invoice_lines: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Dobavi kontekstualne prijedloge na osnovu fakture."""
        if not invoice_lines:
            return []
        
        suggestions = []
        
        try:
            # Analiziraj fakturu za pattern-e
            category = self._detect_product_category(product_name)
            
            # Pronađi slične proizvode u fakturi
            similar_in_invoice = []
            for line in invoice_lines:
                line_name = line.get('naziv_robe', line.get('goods_trade_name', ''))
                if line_name and line_name != product_name:
                    similarity = self._calculate_similarity(product_name, line_name)
                    if similarity > 0.5:
                        similar_in_invoice.append({
                            'name': line_name,
                            'tariff': line.get('tarifni_broj', line.get('tariff_code', '')),
                            'similarity': similarity
                        })
            
            # Ako ima sličnih, predloži isti tarifni broj
            if similar_in_invoice:
                # Sortiraj po sličnosti
                similar_in_invoice.sort(key=lambda x: x['similarity'], reverse=True)
                best_match = similar_in_invoice[0]
                
                if best_match['tariff']:
                    suggestions.append({
                        'tariff_code': best_match['tariff'],
                        'description': best_match['name'],
                        'confidence': best_match['similarity'],
                        'source': 'contextual',
                        'explanation': (
                            f"Sličan proizvod u fakturi: {best_match['name']}. "
                            f"Preporučuje se isti tarifni broj za konzistentnost."
                        ),
                        'needs_review': best_match['similarity'] < 0.7
                    })
            
            # Dodaj warning ako je kategorija nekonzistentna
            invoice_categories = self._analyze_invoice_categories(invoice_lines)
            if category and invoice_categories:
                if category not in invoice_categories and len(invoice_categories) > 0:
                    main_category = max(invoice_categories.items(), key=lambda x: x[1])[0]
                    suggestions.append({
                        'tariff_code': '',
                        'description': f"Upozorenje: {category} u fakturi {main_category}",
                        'confidence': 0.3,
                        'source': 'contextual_warning',
                        'explanation': (
                            f"Proizvod je {category}, ali faktura je uglavnom {main_category}. "
                            f"Provjeri da li je proizvod stvarno dio ove pošiljke."
                        ),
                        'needs_review': True,
                        'is_warning': True
                    })
            
        except Exception as e:
            print(f"⚠️ Greška pri kontekstualnim suggestions: {e}")
        
        return suggestions
    
    def _get_best_suggestion(
        self,
        basic_suggestions: List[Dict[str, Any]],
        agent_suggestions: List[Dict[str, Any]],
        context: DialogContext
    ) -> Optional[EnhancedSuggestionResult]:
        """Odaberi najbolji prijedlog bez dijaloga."""
        all_suggestions = []
        
        # Kombinuj sve prijedloge
        for suggestion in basic_suggestions:
            all_suggestions.append({
                **suggestion,
                'weight': 1.0  # Osnovni prijedlozi imaju punu težinu
            })
        
        for suggestion in agent_suggestions:
            # Historijski prijedlozi imaju veću težinu
            weight = 1.2 if suggestion.get('source') == 'historical' else 1.0
            all_suggestions.append({
                **suggestion,
                'weight': weight
            })
        
        if not all_suggestions:
            return None
        
        # Izračunaj skor za svaki prijedlog
        for suggestion in all_suggestions:
            confidence = suggestion.get('confidence', suggestion.get('similarity', 0.5))
            weight = suggestion.get('weight', 1.0)
            suggestion['score'] = confidence * weight
        
        # Sortiraj po skoru
        all_suggestions.sort(key=lambda x: x['score'], reverse=True)
        
        # Odaberi najbolji
        best = all_suggestions[0]
        
        # Generiši objašnjenje
        explanation = self._generate_explanation(best, context)
        
        return EnhancedSuggestionResult(
            selected_tariff=best['tariff_code'],
            basic_suggestions=basic_suggestions,
            agent_suggestions=agent_suggestions,
            context=context,
            explanation=explanation
        )
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Izračunaj sličnost između dva teksta."""
        if not text1 or not text2:
            return 0.0
        
        from difflib import SequenceMatcher
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
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
        
        return "ostalo"
    
    def _analyze_invoice_categories(
        self,
        invoice_lines: List[Dict]
    ) -> Dict[str, int]:
        """Analiziraj kategorije proizvoda u fakturi."""
        categories = {}
        
        for line in invoice_lines:
            product_name = line.get('naziv_robe', line.get('goods_trade_name', ''))
            if product_name:
                category = self._detect_product_category(product_name)
                categories[category] = categories.get(category, 0) + 1
        
        return categories
    
    def _format_explanation(self, result: Dict[str, Any]) -> str:
        """Formatiraj objašnjenje za basic suggestion."""
        method = result.get('method', '')
        explanation = result.get('explanation', '')
        
        if method == 'mapping':
            return f"Fuzzy match sa postojećim mapiranjem: {explanation}"
        elif method == 'rag':
            return f"Preuzeto iz historijskih podataka: {explanation}"
        elif method == 'ai':
            return f"AI odluka: {explanation}"
        else:
            return explanation
    
    def _generate_explanation(
        self,
        suggestion: Dict[str, Any],
        context: DialogContext
    ) -> str:
        """Generiši objašnjenje za odabrani prijedlog."""
        parts = []
        
        # Dodaj osnovno objašnjenje
        if 'explanation' in suggestion:
            parts.append(suggestion['explanation'])
        
        # Dodaj historijske podatke
        if context.has_historical_data and context.historical_usage_count > 0:
            parts.append(
                f"{context.supplier_name} ima {context.historical_usage_count} "
                f"historijskih deklaracija."
            )
        
        # Dodaj confidence
        confidence = suggestion.get('confidence', suggestion.get('similarity', 0.5))
        parts.append(f"Confidence: {confidence:.0%}")
        
        # Dodaj warnings ako postoje
        if context.warnings:
            parts.append(f"Upozorenja: {', '.join(context.warnings)}")
        
        return ". ".join(parts)
    
    def clear_cache(self):
        """Očisti cache."""
        self.supplier_cache.clear()
        print("🧹 Enhanced suggestion cache cleared")


# Helper funkcija za integraciju sa postojećim sistemom
def get_enhanced_suggestion_for_naimenovanja(
    product_name: str,
    supplier_name: str = "",
    origin_country: str = "",
    invoice_lines: List[Dict] = None,
    show_dialog: bool = True
) -> Optional[str]:
    """
    Helper funkcija za integraciju sa NaimenovanjaController.
    
    Args:
        product_name: Naziv robe
        supplier_name: Dobavljač
        origin_country: Zemlja porijekla
        invoice_lines: Stavke fakture
        show_dialog: Da li prikazati enhanced dijalog
    
    Returns:
        Odabrani tarifni broj ili None
    """
    service = EnhancedTariffSuggestionService()
    
    if show_dialog:
        # Koristi enhanced dijalog
        result = service.suggest_with_context(
            product_name=product_name,
            supplier_name=supplier_name,
            origin_country=origin_country,
            invoice_lines=invoice_lines,
            use_enhanced_dialog=True
        )
        
        if result:
            # Prikaži dijalog
            from gui.dialogs.enhanced_tariff_suggestion_dialog import (
                EnhancedTariffSuggestionDialog
            )
            
            selected = EnhancedTariffSuggestionDialog.show_enhanced_dialog(
                result.basic_suggestions,
                result.agent_suggestions,
                result.context
            )
            
            return selected
    else:
        # Vrati najbolji prijedlog bez dijaloga
        result = service.suggest_with_context(
            product_name=product_name,
            supplier_name=supplier_name,
            origin_country=origin_country,
            invoice_lines=invoice_lines,
            use_enhanced_dialog=False
        )
        
        if result:
            return result.selected_tariff
    
    return None


# Test funkcija
def test_enhanced_service():
    """Testiraj enhanced suggestion servis."""
    print("🧪 Testiranje EnhancedTariffSuggestionService...")
    
    service = EnhancedTariffSuggestionService()
    
    # Test 1: Basic suggestion
    print("\n1. Test basic suggestion:")
    basic = service._get_basic_suggestions("Šrafciger profesionalni", "RS")
    print(f"   Basic suggestions: {len(basic)}")
    for s in basic:
        print(f"     - {s['tariff_code']} ({s['similarity']:.0%})")
    
    # Test 2: Historical suggestions
    print("\n2. Test historical suggestions:")
    historical = service._get_historical_suggestions(
        "Šrafciger",
        "MASTER TOOLS",
        "DE"
    )
    print(f"   Historical suggestions: {len(historical)}")
    
    # Test 3: Full suggestion with context
    print("\n3. Test full suggestion with context:")
    invoice_lines = [
        {"naziv_robe": "Čekić", "tarifni_broj": "82052000"},
        {"naziv_robe": "Ključ", "tarifni_broj": "82054000"},
    ]
    
    result = service.suggest_with_context(
        product_name="Šrafciger",
        supplier_name="MASTER TOOLS",
        origin_country="DE",
        invoice_lines=invoice_lines,
        use_enhanced_dialog=False
    )
    
    if result:
        print(f"   Selected tariff: {result.selected_tariff}")
        print(f"   Explanation: {result.explanation}")
        print(f"   Basic suggestions: {len(result.basic_suggestions)}")
        print(f"   Agent suggestions: {len(result.agent_suggestions)}")
    else:
        print("   ❌ No result")
    
    # Test 4: Helper function
    print("\n4. Test helper function:")
    tariff = get_enhanced_suggestion_for_naimenovanja(
        product_name="Šrafciger",
        supplier_name="MASTER TOOLS",
        show_dialog=False
    )
    print(f"   Suggested tariff: {tariff}")
    
    print("\n✅ Enhanced service testiran!")


if __name__ == "__main__":
    test_enhanced_service()