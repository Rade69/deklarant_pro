"""
Tariff Suggestion Service

Konsolidovani modul koji kombinuje:
1. HybridMatchingService — nisko-nivo matching (istorijsko, keyword, semantic, rules)
2. EnhancedTariffSuggestionService — visoko-nivo orchestracija sa dialogom i kontekstom

Originalni fajlovi: hybrid_matching_service.py + enhanced_tariff_suggestion_service.py
"""

import logging
import re
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from difflib import SequenceMatcher

from database.db import get_db_connection
from services.tariff_mapping_service import TariffMapping
from services.agent.learning.historical_learning_service_safe import HistoricalLearningServiceSafe
from services.agent.learning.supplier_profiling_service import SupplierProfilingService
from services.agent.tariff.hybrid_tariff_agent import HybridTariffAgent
from gui.dialogs.enhanced_tariff_suggestion_dialog import (
    DialogContext,
    create_context_from_invoice
)

logger = logging.getLogger("deklarant_pro.hybrid_matching")


def _is_known_tariff_code(tariff_code: str) -> bool:
    digits = re.sub(r"\D", "", tariff_code or "")
    if not digits:
        return False
    try:
        from services.tariff.tarifa_service import trazi_po_kodu

        return bool(trazi_po_kodu(digits[:8]))
    except Exception as exc:
        logger.warning("Provjera zvanične tarife nije uspjela za %s: %s", tariff_code, exc)
        return True

# ─────────────────────────────────────────────────────────────────────────────
# Dataclasses
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class HybridMatch:
    """Rezultat hybrid matching-a."""
    tariff_mapping: TariffMapping
    confidence: float  # 0.0-1.0
    method: str  # 'historical', 'semantic', 'keyword', 'rules'
    explanation: str


@dataclass
class HybridMatchingResult:
    """Rezultat hybrid matching-a za više stavki."""
    matches: List[HybridMatch]
    avg_confidence: float
    method_distribution: Dict[str, int]


@dataclass
class EnhancedSuggestionResult:
    """Rezultat enhanced suggestion servisa."""
    selected_tariff: str
    basic_suggestions: List[Dict[str, Any]]
    agent_suggestions: List[Dict[str, Any]]
    context: DialogContext
    explanation: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# HybridMatchingService — nisko-nivo matching engine
# ─────────────────────────────────────────────────────────────────────────────

class HybridMatchingService:
    """
    Hybrid Matching Service koji kombinira više metoda.

    Weight distribucija:
    - Istorijsko: 40% (šta je ovaj dobavljač ranije koristio)
    - Semantic: 30% (LLM embedding sličnost)
    - Keyword: 20% (tradicionalni matching)
    - Rules: 10% (carinska pravila)
    """

    def __init__(self):
        self.historical_service = HistoricalLearningServiceSafe()
        self.weights = {
            'historical': 0.40,
            'semantic': 0.30,
            'keyword': 0.20,
            'rules': 0.10
        }
        logger.info("✅ HybridMatchingService inicijalizovan")

    def find_hybrid_mapping(
        self,
        product_code: str,
        naziv_robe: str,
        supplier: str = "",
        country: str = "",
        min_confidence: float = 0.60
    ) -> Optional[HybridMatch]:
        """Pronađi najbolji mapping koristeći hybrid pristup."""
        logger.debug(f"🔍 Hybrid mapping za: '{product_code}', '{naziv_robe[:40]}', supplier='{supplier}'")

        all_candidates = self._get_all_candidates(product_code, naziv_robe, supplier, country)

        if not all_candidates:
            logger.debug(f"ℹ️ Nema kandidata za '{naziv_robe[:40]}'")
            return None

        best_match = self._combine_candidates(all_candidates)

        if best_match and best_match.confidence >= min_confidence:
            logger.debug(f"✅ Hybrid match: {best_match.tariff_mapping.tarifni_broj} "
                         f"(confidence: {best_match.confidence:.1%}, method: {best_match.method})")
            return best_match
        else:
            logger.debug(f"⚠️ Hybrid match below threshold: "
                         f"{best_match.confidence if best_match else 0:.1%} (min: {min_confidence:.1%})")
            return None

    def batch_hybrid_mapping(
        self,
        items: List[Dict[str, Any]],
        supplier: str = "",
        min_confidence: float = 0.60
    ) -> HybridMatchingResult:
        """Batch hybrid mapping za više stavki."""
        matches = []
        method_counts = {'historical': 0, 'semantic': 0, 'keyword': 0, 'rules': 0}

        for i, item in enumerate(items):
            product_code = item.get('product_code', '')
            naziv_robe = item.get('naziv_robe', '')
            country = item.get('zemlja_porijekla', '')

            match = self.find_hybrid_mapping(
                product_code=product_code,
                naziv_robe=naziv_robe,
                supplier=supplier,
                country=country,
                min_confidence=min_confidence
            )

            if match:
                matches.append(match)
                method_counts[match.method] += 1
                logger.debug(f"  [{i+1}] {naziv_robe[:40]}: {match.tariff_mapping.tarifni_broj} "
                             f"({match.confidence:.1%}, {match.method})")
            else:
                logger.debug(f"  [{i+1}] {naziv_robe[:40]}: NO MATCH")

        avg_confidence = sum(m.confidence for m in matches) / len(matches) if matches else 0.0
        logger.info(f"✅ Batch hybrid mapping: {len(matches)}/{len(items)} match-eva "
                    f"(avg confidence: {avg_confidence:.1%})")

        return HybridMatchingResult(
            matches=matches,
            avg_confidence=avg_confidence,
            method_distribution=method_counts
        )

    def get_matching_stats(self) -> Dict[str, Any]:
        """Vrati statistiku matching-a."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) as total FROM catalogs.product_tariff_mapping")
                    total_mappings = cursor.fetchone()['total']
                    cursor.execute("SELECT COUNT(DISTINCT exporter_normalized) as suppliers FROM catalogs.exporter_xml_index")
                    total_suppliers = cursor.fetchone()['suppliers']
                    cursor.execute("SELECT AVG(usage_count) as avg_usage FROM catalogs.product_tariff_mapping")
                    avg_usage = cursor.fetchone()['avg_usage'] or 0
            return {
                'total_mappings': total_mappings,
                'total_suppliers': total_suppliers,
                'avg_usage': round(avg_usage, 1),
                'weights': self.weights,
                'historical_service_available': self.historical_service.is_available()
            }
        except Exception as e:
            logger.debug(f"⚠️ Error getting matching stats: {e}")
            return {}

    # ── Private helpers ───────────────────────────────────────────────────────

    def _get_all_candidates(self, product_code, naziv_robe, supplier, country):
        candidates = []
        if supplier and supplier.strip():
            candidates.extend(self._get_historical_candidates(supplier, product_code, naziv_robe))
        candidates.extend(self._get_keyword_candidates(product_code, naziv_robe))
        candidates.extend(self._get_semantic_candidates(naziv_robe))
        if country and country.strip():
            candidates.extend(self._get_rules_candidates(country, product_code, naziv_robe))
        return candidates

    def _get_historical_candidates(self, supplier, product_code, naziv_robe):
        candidates = []
        try:
            profile = self.historical_service._get_profile_safe(supplier)
            if not profile:
                return candidates
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    if product_code and product_code.strip():
                        cursor.execute("""
                            SELECT DISTINCT ON (commodity_code)
                                   product_code, naziv_robe, commodity_code, precision_1,
                                   zemlja_porijekla, povlastica, usage_count
                            FROM catalogs.product_tariff_mapping
                            WHERE product_code ILIKE %s
                            AND EXISTS (
                                SELECT 1 FROM catalogs.exporter_xml_index
                                WHERE exporter_normalized = %s
                                AND commodity_code = catalogs.product_tariff_mapping.commodity_code
                            )
                            ORDER BY commodity_code, usage_count DESC LIMIT 5
                        """, (product_code.strip(), supplier))
                        for row in cursor.fetchall():
                            mapping = TariffMapping(
                                product_code=row["product_code"], naziv_robe=row["naziv_robe"],
                                tarifni_broj=row["commodity_code"], precision_1=row["precision_1"],
                                zemlja_porijekla=row["zemlja_porijekla"] or "",
                                povlastica=row["povlastica"] or "", usage_count=row["usage_count"],
                                similarity=1.0
                            )
                            confidence = min(row["usage_count"] / 100.0, 1.0) * self.weights['historical']
                            candidates.append(HybridMatch(
                                tariff_mapping=mapping, confidence=confidence, method='historical',
                                explanation=f"Supplier {supplier} ranije koristio ovaj tarifni broj ({row['usage_count']} puta)"
                            ))

                    if not candidates and naziv_robe:
                        keywords = self._extract_keywords(naziv_robe)
                        if keywords:
                            query = f"%{'%'.join(keywords[:3])}%"
                            cursor.execute("""
                                SELECT DISTINCT ON (commodity_code)
                                       product_code, naziv_robe, commodity_code, precision_1,
                                       zemlja_porijekla, povlastica, usage_count
                                FROM catalogs.product_tariff_mapping
                                WHERE naziv_robe ILIKE %s
                                AND EXISTS (
                                    SELECT 1 FROM catalogs.exporter_xml_index
                                    WHERE exporter_normalized = %s
                                    AND commodity_code = catalogs.product_tariff_mapping.commodity_code
                                )
                                ORDER BY commodity_code, usage_count DESC LIMIT 5
                            """, (query, supplier))
                            for row in cursor.fetchall():
                                mapping = TariffMapping(
                                    product_code=row["product_code"], naziv_robe=row["naziv_robe"],
                                    tarifni_broj=row["commodity_code"], precision_1=row["precision_1"],
                                    zemlja_porijekla=row["zemlja_porijekla"] or "",
                                    povlastica=row["povlastica"] or "", usage_count=row["usage_count"],
                                    similarity=1.0
                                )
                                similarity = self._calculate_similarity(naziv_robe, row["naziv_robe"])
                                confidence = similarity * self.weights['historical']
                                candidates.append(HybridMatch(
                                    tariff_mapping=mapping, confidence=confidence, method='historical',
                                    explanation=f"Supplier {supplier} koristio sličan proizvod: {row['naziv_robe'][:50]}"
                                ))
        except Exception as e:
            logger.debug(f"⚠️ Error u istorijskom matching-u za {supplier}: {e}")
        return candidates

    def _get_keyword_candidates(self, product_code, naziv_robe):
        candidates = []
        try:
            from services.tariff_mapping_service import TariffMappingService
            mapping = TariffMappingService().find_mapping(
                product_code=product_code, naziv_robe=naziv_robe, min_similarity=0.70
            )
            if mapping:
                confidence = mapping.similarity * self.weights['keyword']
                candidates.append(HybridMatch(
                    tariff_mapping=mapping, confidence=confidence, method='keyword',
                    explanation=f"Keyword match: similarity={mapping.similarity:.1%}"
                ))
        except Exception as e:
            logger.debug(f"⚠️ Error u keyword matching-u: {e}")
        return candidates

    def _get_semantic_candidates(self, naziv_robe):
        # TODO: Implementirati LLM embedding matching
        return []

    def _get_rules_candidates(self, country, product_code, naziv_robe):
        candidates = []
        try:
            keywords = self._extract_keywords(naziv_robe.lower())
            rules = {
                ('vino', 'RS'): '22042110', ('vino', 'DE'): '22042110',
                ('sir', 'RS'): '04061010',  ('sir', 'DE'): '04061010',
                ('meso', 'RS'): '02013000', ('meso', 'DE'): '02013000',
            }
            for (product_keyword, rule_country), tariff_code in rules.items():
                if country.upper() == rule_country and any(product_keyword in kw for kw in keywords):
                    with get_db_connection() as conn:
                        with conn.cursor() as cursor:
                            cursor.execute("""
                                SELECT product_code, naziv_robe, commodity_code, precision_1,
                                       zemlja_porijekla, povlastica, usage_count
                                FROM catalogs.product_tariff_mapping
                                WHERE commodity_code = %s ORDER BY usage_count DESC LIMIT 1
                            """, (tariff_code,))
                            row = cursor.fetchone()
                            if row:
                                mapping = TariffMapping(
                                    product_code=row["product_code"], naziv_robe=row["naziv_robe"],
                                    tarifni_broj=row["commodity_code"], precision_1=row["precision_1"],
                                    zemlja_porijekla=row["zemlja_porijekla"] or "",
                                    povlastica=row["povlastica"] or "", usage_count=row["usage_count"],
                                    similarity=1.0
                                )
                                candidates.append(HybridMatch(
                                    tariff_mapping=mapping, confidence=self.weights['rules'],
                                    method='rules',
                                    explanation=f"Carinsko pravilo: {product_keyword} iz {country} → {tariff_code}"
                                ))
        except Exception as e:
            logger.debug(f"⚠️ Error u rules matching-u: {e}")
        return candidates

    def _combine_candidates(self, candidates):
        if not candidates:
            return None
        tariff_groups: Dict[str, List[HybridMatch]] = {}
        for candidate in candidates:
            code = candidate.tariff_mapping.tarifni_broj
            tariff_groups.setdefault(code, []).append(candidate)

        best_match, best_confidence = None, 0.0
        for tariff_code, group in tariff_groups.items():
            combined_confidence = sum(c.confidence for c in group)
            methods_used = {c.method for c in group}
            final_confidence = min(combined_confidence + len(methods_used) * 0.05, 1.0)
            if final_confidence > best_confidence:
                best_confidence = final_confidence
                best_match = group[0]
                best_match.confidence = final_confidence
                best_match.explanation = (
                    f"Kombinovani match ({', '.join(sorted(methods_used))}): "
                    f"confidence={final_confidence:.1%}"
                )
        return best_match

    def _extract_keywords(self, text):
        if not text:
            return []
        cleaned = re.sub(r'[^a-zA-ZčćžšđČĆŽŠĐ\s]', ' ', text)
        stop_words = {'i', 'ili', 'sa', 'bez', 'za', 'od', 'do', 'na', 'u', 'po', 'iz', 'kao'}
        return [w for w in cleaned.lower().split() if w not in stop_words and len(w) > 2]

    def _calculate_similarity(self, text1, text2):
        if not text1 or not text2:
            return 0.0
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()


# ─────────────────────────────────────────────────────────────────────────────
# EnhancedTariffSuggestionService — visoko-nivo orchestracija
# ─────────────────────────────────────────────────────────────────────────────

class EnhancedTariffSuggestionService:
    """
    Enhanced servis za sugestije tarifnih brojeva.

    Kombinuje HybridTariffAgent, istorijske podatke, supplier profiling
    i kontekstualne informacije iz fakture.
    """

    def __init__(self):
        self.hybrid_agent = HybridTariffAgent()
        self.historical_service = HistoricalLearningServiceSafe()
        self.profiling_service = SupplierProfilingService()
        self.hybrid_matching = HybridMatchingService()
        self.supplier_cache: Dict[str, Any] = {}

    def suggest_with_context(
        self,
        product_name: str,
        supplier_name: str = "",
        origin_country: str = "",
        invoice_lines: List[Dict] = None,
        use_enhanced_dialog: bool = True
    ) -> Optional[EnhancedSuggestionResult]:
        """Sugeriši tarifni broj sa kontekstualnim informacijama."""
        basic_suggestions = self._get_basic_suggestions(product_name, origin_country)
        agent_suggestions = self._get_agent_suggestions(
            product_name, supplier_name, origin_country, invoice_lines
        )
        context = create_context_from_invoice(
            product_name=product_name,
            supplier_name=supplier_name,
            invoice_lines=invoice_lines or []
        )

        if not use_enhanced_dialog:
            return self._get_best_suggestion(basic_suggestions, agent_suggestions, context)

        return EnhancedSuggestionResult(
            selected_tariff="",
            basic_suggestions=basic_suggestions,
            agent_suggestions=agent_suggestions,
            context=context
        )

    def _get_basic_suggestions(self, product_name, origin_country=""):
        try:
            result = self.hybrid_agent.decide_tariff(
                naziv_robe=product_name, zemlja_porijekla=origin_country
            )
            suggestions = []
            if result.get('tarifni_broj'):
                if _is_known_tariff_code(result['tarifni_broj']):
                    suggestions.append({
                        'tariff_code': result['tarifni_broj'],
                        'description': result.get('explanation', ''),
                        'similarity': result.get('confidence', 0.5),
                        'method': result.get('method', 'ai'),
                        'explanation': self._format_explanation(result),
                        'needs_review': result.get('needs_review', True)
                    })
            for candidate in result.get('candidates', [])[:3]:
                if candidate.get('tarifni_broj'):
                    if not _is_known_tariff_code(candidate['tarifni_broj']):
                        continue
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

    def _get_agent_suggestions(self, product_name, supplier_name, origin_country, invoice_lines):
        suggestions = []
        suggestions.extend(self._get_historical_suggestions(product_name, supplier_name, origin_country))
        suggestions.extend(self._get_hybrid_matching_suggestions(product_name, supplier_name, origin_country))
        suggestions.extend(self._get_contextual_suggestions(product_name, supplier_name, invoice_lines))
        return suggestions

    def _get_historical_suggestions(self, product_name, supplier_name, origin_country):
        if not supplier_name:
            return []
        suggestions = []
        try:
            profile = self.profiling_service.get_complete_profile(supplier_name)
            if profile and profile.product_profiles:
                for product_profile in profile.product_profiles.values():
                    similarity = self.hybrid_matching._calculate_similarity(
                        product_name, product_profile.product_name
                    )
                    if similarity > 0.6:
                        if not _is_known_tariff_code(product_profile.tariff_code):
                            continue
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
            print(f"⚠️ Greška pri dobavljanju istorijskih suggestions: {e}")
        return suggestions

    def _get_hybrid_matching_suggestions(self, product_name, supplier_name, origin_country):
        suggestions = []
        try:
            match_result = self.hybrid_matching.find_hybrid_mapping(
                product_code='', naziv_robe=product_name,
                supplier=supplier_name, country=origin_country, min_confidence=0.50
            )
            if match_result and match_result.tariff_mapping:
                if not _is_known_tariff_code(match_result.tariff_mapping.tarifni_broj):
                    return suggestions
                suggestions.append({
                    'tariff_code': match_result.tariff_mapping.tarifni_broj,
                    'description': match_result.tariff_mapping.naziv_robe,
                    'confidence': match_result.confidence,
                    'source': 'hybrid_matching',
                    'explanation': f"Hybrid matching: {match_result.method} ({match_result.explanation})",
                    'needs_review': match_result.confidence < 0.70
                })
        except Exception as e:
            print(f"⚠️ Greška pri hybrid matching: {e}")
        return suggestions

    def _get_contextual_suggestions(self, product_name, supplier_name, invoice_lines):
        if not invoice_lines:
            return []
        suggestions = []
        try:
            category = self._detect_product_category(product_name)
            similar_in_invoice = []
            for line in invoice_lines:
                line_name = line.get('naziv_robe', line.get('goods_trade_name', ''))
                if line_name and line_name != product_name:
                    similarity = self.hybrid_matching._calculate_similarity(product_name, line_name)
                    if similarity > 0.5:
                        similar_in_invoice.append({
                            'name': line_name,
                            'tariff': line.get('tarifni_broj', line.get('tariff_code', '')),
                            'similarity': similarity
                        })
            if similar_in_invoice:
                similar_in_invoice.sort(key=lambda x: x['similarity'], reverse=True)
                best_match = similar_in_invoice[0]
                if best_match['tariff']:
                    if not _is_known_tariff_code(best_match['tariff']):
                        return suggestions
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
            invoice_categories = self._analyze_invoice_categories(invoice_lines)
            if category and invoice_categories and category not in invoice_categories:
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

    def _get_best_suggestion(self, basic_suggestions, agent_suggestions, context):
        all_suggestions = [
            {**s, 'weight': 1.0} for s in basic_suggestions
        ] + [
            {**s, 'weight': 1.2 if s.get('source') == 'historical' else 1.0}
            for s in agent_suggestions
        ]
        if not all_suggestions:
            return None
        for s in all_suggestions:
            confidence = s.get('confidence', s.get('similarity', 0.5))
            s['score'] = confidence * s.get('weight', 1.0)
        all_suggestions.sort(key=lambda x: x['score'], reverse=True)
        best = all_suggestions[0]
        return EnhancedSuggestionResult(
            selected_tariff=best['tariff_code'],
            basic_suggestions=basic_suggestions,
            agent_suggestions=agent_suggestions,
            context=context,
            explanation=self._generate_explanation(best, context)
        )

    def _detect_product_category(self, product_name):
        p = product_name.lower()
        if any(w in p for w in ['alat', 'šraf', 'čekić', 'ključ']):
            return "ručni alati"
        elif any(w in p for w in ['elektron', 'baterij', 'kabl', 'priključ']):
            return "elektronika"
        elif any(w in p for w in ['keram', 'ploč', 'cigl']):
            return "keramički proizvodi"
        elif any(w in p for w in ['tekstil', 'pamuk', 'tkanin']):
            return "tekstil"
        return "ostalo"

    def _analyze_invoice_categories(self, invoice_lines):
        categories = {}
        for line in invoice_lines:
            name = line.get('naziv_robe', line.get('goods_trade_name', ''))
            if name:
                cat = self._detect_product_category(name)
                categories[cat] = categories.get(cat, 0) + 1
        return categories

    def _format_explanation(self, result):
        method = result.get('method', '')
        explanation = result.get('explanation', '')
        if method == 'mapping':
            return f"Fuzzy match sa postojećim mapiranjem: {explanation}"
        elif method == 'rag':
            return f"Preuzeto iz istorijskih podataka: {explanation}"
        elif method == 'ai':
            return f"AI odluka: {explanation}"
        return explanation

    def _generate_explanation(self, suggestion, context):
        parts = []
        if 'explanation' in suggestion:
            parts.append(suggestion['explanation'])
        if context.has_historical_data and context.historical_usage_count > 0:
            parts.append(
                f"{context.supplier_name} ima {context.historical_usage_count} istorijskih deklaracija."
            )
        confidence = suggestion.get('confidence', suggestion.get('similarity', 0.5))
        parts.append(f"Confidence: {confidence:.0%}")
        if context.warnings:
            parts.append(f"Upozorenja: {', '.join(context.warnings)}")
        return ". ".join(parts)

    def clear_cache(self):
        self.supplier_cache.clear()
        print("🧹 Enhanced suggestion cache cleared")


# ─────────────────────────────────────────────────────────────────────────────
# Helper funkcije (javni API)
# ─────────────────────────────────────────────────────────────────────────────

def get_enhanced_suggestion_for_naimenovanja(
    product_name: str,
    supplier_name: str = "",
    origin_country: str = "",
    invoice_lines: List[Dict] = None,
    show_dialog: bool = True
) -> Optional[str]:
    """Helper funkcija za integraciju sa NaimenovanjaController."""
    service = EnhancedTariffSuggestionService()

    if show_dialog:
        result = service.suggest_with_context(
            product_name=product_name, supplier_name=supplier_name,
            origin_country=origin_country, invoice_lines=invoice_lines,
            use_enhanced_dialog=True
        )
        if result:
            from gui.dialogs.enhanced_tariff_suggestion_dialog import EnhancedTariffSuggestionDialog
            return EnhancedTariffSuggestionDialog.show_enhanced_dialog(
                result.basic_suggestions, result.agent_suggestions, result.context
            )
    else:
        result = service.suggest_with_context(
            product_name=product_name, supplier_name=supplier_name,
            origin_country=origin_country, invoice_lines=invoice_lines,
            use_enhanced_dialog=False
        )
        if result:
            return result.selected_tariff

    return None
