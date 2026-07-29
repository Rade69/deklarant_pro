# Arhitektura: docs/architecture/TARIFF_FACADE_REFACTORING.md

"""
TariffFacade — jedina ulazna tačka za sve tarifne operacije.

Singleton: gradi se jednom, fuzzy indeks ostaje u memoriji.
GUI nikad ne instanzira TariffMappingService/RAGService/HybridAgent direktno.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("deklarant_pro.tariff_facade")

THRESHOLD_DIRECT = 0.85
THRESHOLD_REVIEW = 0.60


@dataclass
class TariffResult:
    tarifni_broj: str
    confidence:   float
    source:       str        # "baza_znanja" | "rag" | "ai" | "nepoznat"
    needs_review: bool
    valid_in_db:  bool = True
    obrazlozenje: str = ""


class TariffFacade:
    """
    Fasada za tarifne servise.

    Upotreba:
        facade = TariffFacade.get_instance()
        result = facade.suggest(naziv_robe, product_code, zemlja)
    """

    _instance: Optional["TariffFacade"] = None

    @classmethod
    def get_instance(cls) -> "TariffFacade":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self._mapping_svc  = None
        self._rag_svc      = None
        self._hybrid_agent = None

    # ------------------------------------------------------------------
    # Lazy init internih servisa
    # ------------------------------------------------------------------

    def _mapping(self):
        if self._mapping_svc is None:
            from services.tariff.tariff_mapping_service import TariffMappingService
            self._mapping_svc = TariffMappingService()
            logger.info("TariffMappingService inicijalizovan (fuzzy indeks u memoriji)")
        return self._mapping_svc

    def _rag(self):
        if self._rag_svc is None:
            from services.agent.tariff.tariff_rag_service import TariffRAGService
            self._rag_svc = TariffRAGService()
        return self._rag_svc

    def _agent(self):
        if self._hybrid_agent is None:
            from services.agent.tariff.hybrid_tariff_agent import HybridTariffAgent
            self._hybrid_agent = HybridTariffAgent()
            logger.info("HybridTariffAgent inicijalizovan (tariff cache u memoriji)")
        return self._hybrid_agent

    # ------------------------------------------------------------------
    # Javni API — docs/architecture/TARIFF_FACADE_REFACTORING.md
    # ------------------------------------------------------------------

    def suggest(
        self,
        naziv_robe:   str,
        product_code: str = "",
        zemlja:       str = "",
    ) -> TariffResult:
        """
        Level 1 → 2 → 3 pipeline za jedan naziv robe.
        Vraća TariffResult sa confidence, source i needs_review.
        """
        naziv_robe = (naziv_robe or "").strip()
        if not naziv_robe:
            return self._empty_result()

        # Level 1: baza znanja (fuzzy, brzo)
        result = self._try_mapping(naziv_robe, product_code)
        if result:
            return result

        # Level 2: PostgreSQL RAG (istorija + zvanična tarifa)
        result = self._try_rag(naziv_robe, zemlja)
        if result:
            return result

        # Level 3: AI (Groq/Ollama, samo ako L1 i L2 nisu sigurni)
        return self._try_ai(naziv_robe, zemlja)

    def batch_suggest(self, items: list) -> list[TariffResult]:
        """
        Batch obrada za auto-fill dugme u faktura_view.
        items: lista InvoiceLine objekata ili dict-ova sa 'naziv_robe', 'product_code', 'zemlja_porijekla'.
        """
        results = []
        for item in items:
            if hasattr(item, "naziv_robe"):
                naziv       = (item.naziv_robe or "").strip()
                product_code = (getattr(item, "product_code", "") or "").strip()
                zemlja      = (getattr(item, "zemlja_porijekla", "") or "").strip()
            else:
                naziv        = (item.get("naziv_robe", "") or "").strip()
                product_code = (item.get("product_code", "") or "").strip()
                zemlja       = (item.get("zemlja_porijekla", "") or "").strip()

            results.append(self.suggest(naziv, product_code, zemlja))

        return results

    def validate(self, tarifni_broj: str) -> bool:
        """
        Provjera da li je tarifni broj validan u zvanicna_tarifa.
        O(1) — koristi in-memory cache iz HybridTariffAgent.
        """
        try:
            from services.agent.tariff.hybrid_tariff_agent import _validate_tariff_number
            return _validate_tariff_number(tarifni_broj)
        except Exception:
            return True  # graceful degradation

    def learn(
        self,
        product_code:    str,
        naziv_robe:      str,
        tarifni_broj:    str,
        confidence:      float = 1.0,
        zemlja_porijekla: str = "",
        povlastica:      str = "",
        precision_1:     str = "",
    ) -> None:
        """Upisuje novo mapiranje u bazu znanja (auto-učenje iz ručnih ispravki)."""
        try:
            self._mapping().save_mapping(
                product_code=product_code,
                naziv_robe=naziv_robe,
                tarifni_broj=tarifni_broj,
                zemlja_porijekla=zemlja_porijekla,
                povlastica=povlastica,
                precision_1=precision_1,
            )
        except Exception as e:
            logger.warning(f"learn() greška: {e}")

    def sync_mapping(
        self,
        naziv_robe:      str,
        product_code:    str,
        new_tariff:      str,
        zemlja_porijekla: str = "",
        precision_1:     str = "",
        old_tariff:      str = "",
    ) -> int:
        """Obriši stare zapise sa pogrešnom tarifom i sačuvaj novi.

        Objedinjuje duplikat logiku iz NaimenovanjaView (l.1791 i l.2457).

        Args:
            naziv_robe: naziv robe za ILIKE pretragu
            product_code: šifra proizvoda (može biti prazno)
            new_tariff: nova (tačna) tarifa koja se čuva
            zemlja_porijekla: zemlja porijekla
            precision_1: sufiks tarife (npr. '000')
            old_tariff: ako je dato, briše SAMO zapise sa ovom tarifom
                       (selektivni mod); inače briše sve zapise sa
                       drugom tarifom (agresivni mod)

        Returns:
            Broj obrisanih zapisa.
        """
        if not naziv_robe:
            return 0
        deleted = 0
        try:
            from database.db import get_db_connection
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    if old_tariff:
                        # Selektivni mod: briši samo staru tarifu
                        cursor.execute(
                            """
                            DELETE FROM catalogs.product_tariff_mapping
                            WHERE (naziv_robe ILIKE %s OR product_code = %s)
                              AND commodity_code = %s
                            """,
                            (f"%{naziv_robe}%", product_code or "__NONE__", old_tariff),
                        )
                    else:
                        # Agresivni mod: briši sve osim nove tarife
                        cursor.execute(
                            """
                            DELETE FROM catalogs.product_tariff_mapping
                            WHERE (naziv_robe ILIKE %s OR product_code = %s)
                              AND commodity_code != %s
                            """,
                            (f"%{naziv_robe}%", product_code or "__NONE__", new_tariff),
                        )
                    deleted = cursor.rowcount
        except Exception as e:
            logger.warning(f"sync_mapping() DELETE greška: {e}")

        # Sačuvaj novi tarif
        if new_tariff:
            self.learn(
                product_code=product_code or "",
                naziv_robe=naziv_robe,
                tarifni_broj=new_tariff,
                zemlja_porijekla=zemlja_porijekla,
                povlastica="",
                precision_1=precision_1,
            )
        return deleted

    def increment_usage(
        self,
        tarifni_broj: str,
        product_code: Optional[str],
        naziv_robe:   str,
    ) -> None:
        """Povećava usage_count u bazi znanja — zove se kad korisnik prihvati prijedlog."""
        try:
            self._mapping()._increment_usage(tarifni_broj, product_code, naziv_robe)
        except Exception as e:
            logger.warning(f"increment_usage() greška: {e}")

    # ------------------------------------------------------------------
    # Interni koraci
    # ------------------------------------------------------------------

    def _try_mapping(self, naziv_robe: str, product_code: str) -> Optional[TariffResult]:
        try:
            r = self._mapping().find_mapping(
                product_code=product_code,
                naziv_robe=naziv_robe,
                min_similarity=0.70,
            )
            if r and hasattr(r, "tarifni_broj") and r.tarifni_broj:
                conf = float(getattr(r, "similarity", 0.70))
                return TariffResult(
                    tarifni_broj=r.tarifni_broj,
                    confidence=conf,
                    source="baza_znanja",
                    needs_review=conf < THRESHOLD_REVIEW,
                )
        except Exception as e:
            logger.warning(f"_try_mapping greška: {e}")
        return None

    def _try_rag(self, naziv_robe: str, zemlja: str) -> Optional[TariffResult]:
        try:
            rag_result = self._rag().search(naziv_robe, limit=5, zemlja_porijekla=zemlja)
            top = rag_result.get("top_result")
            if top and top.get("tarifni_kod"):
                conf = float(top.get("confidence", 0.0))
                if conf >= THRESHOLD_REVIEW:
                    return TariffResult(
                        tarifni_broj=top["tarifni_kod"],
                        confidence=conf,
                        source="rag",
                        needs_review=conf < THRESHOLD_REVIEW,
                    )
        except Exception as e:
            logger.warning(f"_try_rag greška: {e}")
        return None

    def _try_ai(self, naziv_robe: str, zemlja: str) -> TariffResult:
        try:
            r = self._agent().decide_tariff(naziv_robe, zemlja_porijekla=zemlja)
            return TariffResult(
                tarifni_broj=r.get("tarifni_broj", ""),
                confidence=r.get("confidence", 0.0),
                source="ai",
                needs_review=r.get("needs_review", True),
                valid_in_db=r.get("valid_in_db", True),
                obrazlozenje=r.get("obrazlozenje", ""),
            )
        except Exception as e:
            logger.warning(f"_try_ai greška: {e}")
            return self._empty_result()

    def auto_populate_tariffs(self, invoice_lines: list, **kwargs):
        """
        Batch auto-popunjavanje tarifnih brojeva za sve stavke fakture.
        Pass-through na TariffMappingService.auto_populate_tariffs()
        (uklj. dry_run=True za preview bez upisa — vidi commit_proposals()).
        Koristi faktura_view za auto-fill dugme.
        """
        return self._mapping().auto_populate_tariffs(invoice_lines, **kwargs)

    def commit_proposals(self, invoice_lines: list, proposals: list):
        """
        Upiši prijedloge iz auto_populate_tariffs(dry_run=True) bez ponovnog
        računanja. Pass-through na TariffMappingService.commit_proposals().
        """
        return self._mapping().commit_proposals(invoice_lines, proposals)

    def learn_from_draft(self, invoice_lines: list, draft_uid: str = "") -> int:
        """
        Uči iz već kreiranih naimenovanja — sprema mappinge u bazu znanja.
        Pass-through na TariffMappingService.learn_from_draft().

        draft_uid: identitet deklaracije za dedup ledger (vidi
        project_rooms/2026-07-28_tarifno-ucenje-dedup-po-deklaraciji.md) —
        prazan string zadrzava stari nezasticeni put.
        """
        try:
            return self._mapping().learn_from_draft(invoice_lines, draft_uid=draft_uid)
        except Exception as e:
            logger.warning(f"learn_from_draft() greška: {e}")
            return 0

    def import_from_xml_files(self, filepaths: list) -> dict:
        """
        Uvozi mappinge iz ASYCUDA XML fajlova u bazu znanja.
        Pass-through na TariffMappingService.import_from_xml_files().
        """
        try:
            return self._mapping().import_from_xml_files(filepaths)
        except Exception as e:
            logger.warning(f"import_from_xml_files() greška: {e}")
            return {"total_files": 0, "total_items": 0, "imported": 0, "skipped": 0}

    def suggest_fast(
        self,
        naziv_robe:   str,
        product_code: str = "",
    ) -> Optional[TariffResult]:
        """
        Samo Level 1 (baza znanja, bez DB i AI).
        Koristi tariff_llm_worker za pre-filter prije batch LLM poziva.
        Vraća None ako nema dovoljno sigurnog rezultata.
        """
        return self._try_mapping((naziv_robe or "").strip(), product_code or "")

    def rag_candidates(self, naziv_robe: str, zemlja: str = "", limit: int = 5) -> list:
        """
        Level 2 kandidati iz zvanicna_tarifa za kontekst batch LLM poziva.
        Vraća listu dict-ova sa 'tarifni_kod' i 'naziv_robe'.
        """
        try:
            return self._rag().search_official(naziv_robe, limit=limit)
        except Exception as e:
            logger.warning(f"rag_candidates greška: {e}")
            return []

    def _empty_result(self) -> TariffResult:
        return TariffResult(
            tarifni_broj="",
            confidence=0.0,
            source="nepoznat",
            needs_review=True,
            valid_in_db=False,
        )
