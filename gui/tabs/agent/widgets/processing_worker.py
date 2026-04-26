"""
ProcessingWorker - background thread za procesiranje fajlova.

Koristi PRIVATNU ImportService instancu (ne singleton) da izbjegne
race condition sa main threadom oko last_import_type stanja:
- ImportService SAM detektuje parove (Excel + PDF)
- ImportService SAM kombinuje podatke
- ImportService SAM popunjava teÅ¾ine, zemlje, izjave o porijeklu
"""
from PySide6.QtCore import QThread, Signal
from pathlib import Path
import re
from gui.tabs.agent.models.file_item import FileItem


class ProcessingWorker(QThread):
    """Background thread koji parsira fajlove koristeÄ‡i import_service."""

    progress = Signal(str)             # poruka za activity log
    file_started = Signal(str)         # filepath - poÄelo procesiranje fajla
    file_completed = Signal(object)    # FileItem - fajl zavrÅ¡en
    all_completed = Signal(list)       # List[FileItem] - sve zavrÅ¡eno
    error_occurred = Signal(str, str)  # filepath, error_message

    def __init__(self, files: list, parent=None):
        super().__init__(parent)
        self.files = files  # List[FileItem]
        self._cancelled = False

    def cancel(self):
        """OtkaÅ¾i procesiranje."""
        self._cancelled = True

    def run(self):
        """
        Glavni thread loop â€” koristi PRIVATNU ImportService instancu.

        FIX: PreskaÄe packing listove ako je odgovarajuÄ‡a faktura veÄ‡
        parsirana sa automatskom kombinacijom (BlagiÄ‡-Attos).
        """
        import time
        import gc
        total_start = time.time()

        from services.import_service import ImportService
        from importers.import_result import ImportResult
        from importers.blagic_attos_importer import find_matching_packing_list, is_blagic_attos_packing_list

        # â­ PRIVATNA instanca ImportService-a za worker thread.
        # NIKAD ne koristiti singleton (get_import_service) ovdje â€” singleton dijeli
        # last_import_type/path/result stanje sa main threadom â†’ race condition koji
        # razbija Excel+PDF par kombinovanje za 2.+ fakturu u isti batch.
        svc = ImportService()
        svc.clear_memory()

        # DOC: scripts/master_frigo_agent_import_2026-04-26.md
        # â­ Sortiranje po normalizovanom broju fakture:
        #   - poveÄ‡ava Å¡ansu da Excel+PDF parovi budu susjedni (import_service kombinuje samo "previous + current")
        #   - mapping xlsx (tarife/porekla/podela) ide POSLIJE PDF-a da ne pravi laÅ¾ne standalone uvoze
        sorted_files = sorted(self.files, key=self._pair_sort_key)

        # â­ TRACKING: Koji fajlovi su veÄ‡ "potroÅ¡eni" kroz kombinaciju
        consumed_files: set[str] = set()
        pdf_folders: set[str] = {
            str(Path(f.filepath).parent)
            for f in sorted_files
            if Path(f.filepath).suffix.lower() == ".pdf"
        }

        self.progress.emit(f"ðŸ“Š Ukupno fajlova: {len(sorted_files)}")
        self.progress.emit(f"ðŸ” import_service: {svc}")
        self.progress.emit(f"ðŸ“‹ Redoslijed: {[f.filename for f in sorted_files]}")

        # â­ Uvozi redom - import_service SAM radi sve!
        for file_item in sorted_files:
            if self._cancelled:
                break

            # Mapping Excel (tarife/porekla/podela) nije faktura.
            # Ako u istom folderu postoji PDF u ovom batch-u, mapping xlsx preskaÄemo.
            if self._is_mapping_xlsx(file_item.filepath) and str(Path(file_item.filepath).parent) in pdf_folders:
                self.progress.emit(f"   â­ï¸ PreskaÄem mapping Excel: {file_item.filename}")
                file_item.status = 'Skipped'
                file_item.invoice_lines = []
                self.file_completed.emit(file_item)
                continue

            # â­ PRESKOÄŒI ako je veÄ‡ potroÅ¡en kroz kombinaciju fakture
            if file_item.filepath in consumed_files:
                self.progress.emit(f"   â­ï¸ PreskaÄem (veÄ‡ kombinovano sa fakturu): {file_item.filename}")
                file_item.status = 'Skipped'
                file_item.invoice_lines = []
                self.file_completed.emit(file_item)
                continue

            file_start = time.time()
            self.file_started.emit(file_item.filepath)
            self.progress.emit(f"\nðŸ“„ Parsing: {file_item.filename}")
            self.progress.emit(f"   ðŸ“ Tip: {file_item.file_type}")

            try:
                # â­ KORISTI PRIVATNU ImportService INSTANCU
                self.progress.emit(f"   ðŸ”„ import_service.import_file()...")
                result = svc.import_file(str(file_item.filepath))

                if isinstance(result, ImportResult):
                    invoice_lines = result.items

                    # â­ SaÄuvaj SVE podatke iz ImportResult
                    file_item.invoice_number = result.invoice_name or ""  # â­ BROJ FAKTURE IZ PDF-A
                    file_item.bruto_kg = result.bruto_kg
                    file_item.neto_kg = result.neto_kg
                    file_item.has_origin_statement = result.has_origin_statement
                    file_item.origin_statements = result.origin_statements
                    file_item.is_authorized_exporter = any(
                        getattr(s, 'tip_izjave', '') == 'ovlaseni_izvoznik'
                        for s in (result.origin_statements or [])
                    )
                    file_item.is_combined = result.is_combined  # â­ KLJUÄŒNO za duplikat detekciju
                    file_item.consumed_paths = list(getattr(result, "consumed_paths", []) or [])
                    file_item.invoice_lines = invoice_lines
                    file_item.status = 'Completed'
                    file_item.detected_parser = getattr(result, '_detected_format', 'auto') or 'auto'
                    file_item.confidence = 1.0 if invoice_lines else 0.4

                    # â­ KLJUÄŒNO: Da li je kombinovano?
                    if result.is_combined:
                        self.progress.emit(f"   âœ… KOMBINOVANO (Excel+PDF): {len(invoice_lines)} stavki")
                        self.progress.emit(f"   âš–ï¸ Bruto: {result.bruto_kg:.2f}kg, Neto: {result.neto_kg:.2f}kg")
                        if result.has_origin_statement:
                            self.progress.emit(f"   ðŸŒ IZJAVA O PORIJEKLU: DA ({len(result.origin_statements or [])} izjava)")
                        else:
                            self.progress.emit(f"   ðŸŒ IZJAVA O PORIJEKLU: NE")
                    else:
                        self.progress.emit(f"   ðŸ“„ Single import: {len(invoice_lines)} stavki")
                        self.progress.emit(f"   âš–ï¸ Bruto: {result.bruto_kg:.2f}kg, Neto: {result.neto_kg:.2f}kg")
                    # PrikaÅ¾i warnings (npr. neto nije pronaÄ‘en)
                    for w in getattr(result, 'warnings', []):
                        self.progress.emit(f"   {w}")

                    # â­ FIX: Ako je ovo BlagiÄ‡-Attos faktura sa auto-kombinacijom,
                    #   oznaÄi odgovarajuÄ‡i packing list kao "potroÅ¡en"
                    detected_format = getattr(result, '_detected_format', '') or ''
                    if 'blagic_attos' in detected_format.lower() or 'attos' in detected_format.lower():
                        packing_path = find_matching_packing_list(str(file_item.filepath))
                        if packing_path:
                            consumed_files.add(packing_path)
                            self.progress.emit(f"   ðŸ“Ž Packing list oznaÄen kao potroÅ¡en: {Path(packing_path).name}")

                    # â­ FIX: Ako je import interno koristio drugi fajl (npr. LeburiÄ‡ Excel Äita PDF),
                    #   oznaÄi te fajlove kao "potroÅ¡ene" â€” agent ih ne treba obraÄ‘ivati ponovo.
                    #   Ako je fajl VEÄ† obraÄ‘en (npr. Excel koji je bio par za PDF), retroaktivno
                    #   ga oznaÄi kao Skipped i oÄisti linije da se ne duplikata u draftu.
                    for cp in getattr(result, 'consumed_paths', []):
                        consumed_files.add(cp)
                        # Retroaktivno oznaÄi file_item ako je veÄ‡ obraÄ‘en
                        for prev in sorted_files:
                            if prev.filepath == cp and prev.status == 'Completed':
                                prev.status = 'Skipped'
                                prev.invoice_lines = []
                                self.progress.emit(f"   ðŸ”— Kombinirani par â€” preskaÄem prethodni: {Path(cp).name}")
                                self.file_completed.emit(prev)  # AÅ¾uriraj status u tabeli
                                break
                        else:
                            self.progress.emit(f"   ðŸ“Ž Interno koriÅ¡ten fajl preskoÄen: {Path(cp).name}")
                elif isinstance(result, list):
                    # Fallback na listu
                    invoice_lines = result
                    file_item.invoice_lines = invoice_lines
                    file_item.status = 'Completed'
                    file_item.detected_parser = 'auto'
                    file_item.confidence = 1.0 if invoice_lines else 0.4
                    self.progress.emit(f"   âœ… List: {len(invoice_lines)} stavki")
                else:
                    file_item.status = 'Error'
                    file_item.error_message = "Nema rezultata"
                    self.progress.emit(f"   âŒ Nema rezultata")

                file_elapsed = time.time() - file_start
                self.progress.emit(f"   â±ï¸ Vrijeme: {file_elapsed:.1f}s")
                self.file_completed.emit(file_item)

            except MemoryError:
                file_item.status = 'Error'
                file_item.error_message = "Nedovoljno memorije za parsiranje fajla"
                self.error_occurred.emit(file_item.filepath, file_item.error_message)
                self.progress.emit(f"   âŒ MemoryError â€” pokuÅ¡aj sa manjim brojem fajlova odjednom")
                self.file_completed.emit(file_item)
                gc.collect()

            except Exception as e:
                import traceback
                file_item.status = 'Error'
                file_item.error_message = str(e)
                self.error_occurred.emit(file_item.filepath, str(e))
                self.progress.emit(f"   âŒ GreÅ¡ka: {e}")
                self.progress.emit(f"   ðŸ“‹ Stack: {traceback.format_exc()}")
                self.file_completed.emit(file_item)

            finally:
                # gc.collect() samo za PDF fajlove (pdfplumber alocira viÅ¡e objekata)
                # ili svakih 5 fajlova â€” Excel/mapping fajlovi ne zahtijevaju cleanup
                _is_pdf = Path(file_item.filepath).suffix.lower() == ".pdf"
                _file_no = getattr(self, '_gc_counter', 0) + 1
                self._gc_counter = _file_no
                if _is_pdf or _file_no % 5 == 0:
                    gc.collect()

        # Post-process za Agent workflow:
        # Master Frigo PDF + Excel sparivanje u istom batch-u (cijena/iznos iz Excel-a)
        try:
            self._postprocess_master_frigo_pairs(sorted_files)
        except Exception as e:
            self.progress.emit(f"âš ï¸ Master Frigo post-process greÅ¡ka: {e}")

        # Ukupno vrijeme
        total_elapsed = time.time() - total_start
        self.progress.emit(f"\n{'='*60}")
        self.progress.emit(f"â±ï¸ UKUPNO: {total_elapsed:.1f}s")
        self.progress.emit(f"ðŸ“Š Prosjek: {total_elapsed/len(self.files):.1f}s po fajlu")
        self.progress.emit(f"{'='*60}\n")

        self.all_completed.emit(sorted_files)

    @staticmethod
    def _normalize_code(value: str) -> str:
        if not value:
            return ""
        return re.sub(r"[^a-z0-9]", "", value.lower())

    @staticmethod
    def _has_financials(line) -> bool:
        return bool((getattr(line, "iznos", 0) or 0) > 0 or (getattr(line, "cijena_jed", 0) or 0) > 0)

    @classmethod
    def _apply_excel_financials(cls, pdf_lines: list, excel_lines: list) -> int:
        """PrepiÅ¡i finansijske podatke iz Excel-a u PDF stavke (primarno po product_code)."""
        code_map = {}
        name_map = {}
        for el in excel_lines or []:
            if not cls._has_financials(el):
                continue
            c = cls._normalize_code(getattr(el, "product_code", "") or "")
            n = cls._normalize_code(getattr(el, "naziv_robe", "") or "")
            if c and c not in code_map:
                code_map[c] = el
            if n and n not in name_map:
                name_map[n] = el

        enriched = 0
        for pl in pdf_lines or []:
            match = None
            c = cls._normalize_code(getattr(pl, "product_code", "") or "")
            if c:
                match = code_map.get(c)
            if not match:
                n = cls._normalize_code(getattr(pl, "naziv_robe", "") or "")
                if n:
                    match = name_map.get(n)
            if not match:
                continue

            changed = False
            if (getattr(pl, "cijena_jed", 0) or 0) <= 0 and (getattr(match, "cijena_jed", 0) or 0) > 0:
                pl.cijena_jed = match.cijena_jed
                changed = True
            if (getattr(pl, "iznos", 0) or 0) <= 0 and (getattr(match, "iznos", 0) or 0) > 0:
                pl.iznos = match.iznos
                changed = True
            if (getattr(pl, "kolicina", 0) or 0) <= 0 and (getattr(match, "kolicina", 0) or 0) > 0:
                pl.kolicina = match.kolicina
                changed = True

            if changed:
                enriched += 1

        return enriched

    @staticmethod
    def _is_master_frigo_pdf_item(file_item: FileItem) -> bool:
        if file_item.status != "Completed" or not file_item.invoice_lines:
            return False
        if file_item.file_type != "PDF":
            return False
        parser = (file_item.detected_parser or "").lower()
        return "master_frigo" in parser

    def _postprocess_master_frigo_pairs(self, files: list[FileItem]) -> None:
        """
        Agent-level sparivanje Master Frigo PDF + Excel:
        - po normalizovanom tokenu fakture
        - finansije (cijena/iznos/kolicina) prepisuju se iz Excel-a u PDF stavke
        - Excel se markira kao Skipped da ne uÄ‘e kao posebna faktura
        """
        excel_by_token: dict[str, list[FileItem]] = {}
        for f in files:
            if f.status != "Completed" or f.file_type != "Excel" or not f.invoice_lines:
                continue
            token = self._normalized_invoice_token(f.filepath)
            excel_by_token.setdefault(token, []).append(f)

        for pdf_item in files:
            if not self._is_master_frigo_pdf_item(pdf_item):
                continue
            token = self._normalized_invoice_token(pdf_item.filepath)
            candidates = excel_by_token.get(token) or []
            if not candidates:
                continue

            excel_item = candidates[0]
            enriched = self._apply_excel_financials(pdf_item.invoice_lines, excel_item.invoice_lines)
            if enriched <= 0:
                continue

            pdf_item.is_combined = True
            excel_item.status = "Skipped"
            excel_item.invoice_lines = []
            self.progress.emit(
                f"   ðŸ”— Master Frigo pair: {Path(pdf_item.filepath).name} + {Path(excel_item.filepath).name} "
                f"(aÅ¾urirano finansija: {enriched} stavki)"
            )
            self.file_completed.emit(excel_item)

    @staticmethod
    def _normalized_invoice_token(filepath: str) -> str:
        """Normalizuje naziv fajla za sparivanje parova (isti princip kao import_service)."""
        stem = Path(filepath).stem.lower()
        stem = stem.replace("-", "").replace("_", "").replace(" ", "")
        for kw in ("packing", "list", "pl", "invoice", "inv", "faktura"):
            stem = stem.replace(kw, "")
        stem = re.sub(r"[^a-z0-9]", "", stem)
        return stem

    @staticmethod
    def _natural_invoice_parts(value: str) -> tuple:
        token = ProcessingWorker._normalized_invoice_token(value)
        parts = re.findall(r"\d+|[a-z]+", token)
        # Sve dijelove pretvoriti u str (brojevi zero-padded) da se izbjegne
        # TypeError: '<' not supported between instances of 'int' and 'str'
        return tuple(part.zfill(10) if part.isdigit() else part for part in parts)

    @staticmethod
    def _is_mapping_xlsx(filepath: str) -> bool:
        """Da li je ovo globalni mapping excel (Master Frigo i sliÄni)."""
        p = Path(filepath)
        if p.suffix.lower() not in (".xlsx", ".xls", ".xlsm"):
            return False
        name = p.name.lower()
        return any(
            marker in name
            for marker in (
                "tarife",
                "podela",
                "porekla",
                "poreklu",
                "poreklo",
                "porijekla",
                "porijeklu",
                "ptp",
                "15467",
            )
        )

    @classmethod
    def _pair_sort_key(cls, file_item: FileItem):
        p = Path(file_item.filepath)
        ext = p.suffix.lower()
        token = cls._normalized_invoice_token(file_item.filepath)
        is_mapping = cls._is_mapping_xlsx(file_item.filepath)

        # Normalni Excel prije PDF (za combine sluÄajeve), mapping Excel na kraj grupe
        if is_mapping:
            priority = 2
        elif ext in (".xlsx", ".xls", ".xlsm"):
            priority = 0
        elif ext == ".pdf":
            priority = 1
        else:
            priority = 3

        # Mapping fajlovi idu globalno na kraj reda da ne kvare sequence previous+current.
        return (1 if is_mapping else 0, cls._natural_invoice_parts(file_item.filepath), priority, token, p.name.lower())

    @staticmethod
    def _normalize_code(value: str) -> str:
        if not value:
            return ""
        return re.sub(r"[^a-z0-9]", "", value.lower())

    @staticmethod
    def _has_financials(line) -> bool:
        return bool((getattr(line, "iznos", 0) or 0) > 0 or (getattr(line, "cijena_jed", 0) or 0) > 0)

    @classmethod
    def _apply_excel_financials(cls, pdf_lines: list, excel_lines: list) -> int:
        """PrepiÅ¡i finansijske podatke iz Excel-a u PDF stavke (primarno po product_code)."""
        code_map = {}
        name_map = {}
        for el in excel_lines or []:
            if not cls._has_financials(el):
                continue
            c = cls._normalize_code(getattr(el, "product_code", "") or "")
            n = cls._normalize_code(getattr(el, "naziv_robe", "") or "")
            if c and c not in code_map:
                code_map[c] = el
            if n and n not in name_map:
                name_map[n] = el

        enriched = 0
        for pl in pdf_lines or []:
            match = None
            c = cls._normalize_code(getattr(pl, "product_code", "") or "")
            if c:
                match = code_map.get(c)
            if not match:
                n = cls._normalize_code(getattr(pl, "naziv_robe", "") or "")
                if n:
                    match = name_map.get(n)
            if not match:
                continue

            changed = False
            if (getattr(pl, "cijena_jed", 0) or 0) <= 0 and (getattr(match, "cijena_jed", 0) or 0) > 0:
                pl.cijena_jed = match.cijena_jed
                changed = True
            if (getattr(pl, "iznos", 0) or 0) <= 0 and (getattr(match, "iznos", 0) or 0) > 0:
                pl.iznos = match.iznos
                changed = True
            if (getattr(pl, "kolicina", 0) or 0) <= 0 and (getattr(match, "kolicina", 0) or 0) > 0:
                pl.kolicina = match.kolicina
                changed = True

            if changed:
                enriched += 1

        return enriched

    @staticmethod
    def _is_master_frigo_pdf_item(file_item: FileItem) -> bool:
        if file_item.status != "Completed" or not file_item.invoice_lines:
            return False
        if file_item.file_type != "PDF":
            return False
        parser = (file_item.detected_parser or "").lower()
        return "master_frigo" in parser

    def _postprocess_master_frigo_pairs(self, files: list[FileItem]) -> None:
        """
        Agent-level sparivanje Master Frigo PDF + Excel:
        - po normalizovanom tokenu fakture
        - finansije (cijena/iznos/kolicina) prepisuju se iz Excel-a u PDF stavke
        - Excel se markira kao Skipped da ne uÄ‘e kao posebna faktura
        """
        excel_by_token: dict[str, list[FileItem]] = {}
        for f in files:
            if f.status != "Completed" or f.file_type != "Excel" or not f.invoice_lines:
                continue
            token = self._normalized_invoice_token(f.filepath)
            excel_by_token.setdefault(token, []).append(f)

        for pdf_item in files:
            if not self._is_master_frigo_pdf_item(pdf_item):
                continue
            token = self._normalized_invoice_token(pdf_item.filepath)
            candidates = excel_by_token.get(token) or []
            if not candidates:
                continue

            excel_item = candidates[0]
            enriched = self._apply_excel_financials(pdf_item.invoice_lines, excel_item.invoice_lines)
            if enriched <= 0:
                continue

            pdf_item.is_combined = True
            excel_item.status = "Skipped"
            excel_item.invoice_lines = []
            self.progress.emit(
                f"   ðŸ”— Master Frigo pair: {Path(pdf_item.filepath).name} + {Path(excel_item.filepath).name} "
                f"(aÅ¾urirano finansija: {enriched} stavki)"
            )
            self.file_completed.emit(excel_item)

    @staticmethod
    def _normalized_invoice_token(filepath: str) -> str:
        """Normalizuje naziv fajla za sparivanje parova (isti princip kao import_service)."""
        stem = Path(filepath).stem.lower()
        stem = stem.replace("-", "").replace("_", "").replace(" ", "")
        for kw in ("packing", "list", "pl", "invoice", "inv", "faktura"):
            stem = stem.replace(kw, "")
        stem = re.sub(r"[^a-z0-9]", "", stem)
        return stem

    @staticmethod
    def _is_mapping_xlsx(filepath: str) -> bool:
        """Da li je ovo globalni mapping excel (Master Frigo i sliÄni)."""
        p = Path(filepath)
        if p.suffix.lower() not in (".xlsx", ".xls", ".xlsm"):
            return False
        name = p.name.lower()
        return any(
            marker in name
            for marker in (
                "tarife",
                "podela",
                "porekla",
                "poreklu",
                "poreklo",
                "porijekla",
                "porijeklu",
            )
        )

    @classmethod
    def _pair_sort_key(cls, file_item: FileItem):
        p = Path(file_item.filepath)
        ext = p.suffix.lower()
        token = cls._normalized_invoice_token(file_item.filepath)
        is_mapping = cls._is_mapping_xlsx(file_item.filepath)

        # Normalni Excel prije PDF (za combine sluÄajeve), mapping Excel na kraj grupe
        if is_mapping:
            priority = 2
        elif ext in (".xlsx", ".xls", ".xlsm"):
            priority = 0
        elif ext == ".pdf":
            priority = 1
        else:
            priority = 3

        # Mapping fajlovi idu globalno na kraj reda da ne kvare sequence previous+current.
        return (1 if is_mapping else 0, token, priority, p.name.lower())

    def _parse_xml(self, file_item: FileItem, filepath: Path) -> list:
        """Parsira XML fajl."""
        try:
            from importers.xml_importer import XMLImporter
            importer = XMLImporter()
            result = importer.import_file(filepath)
            file_item.detected_parser = 'XML'
            return result.get('items', [])
        except ImportError:
            # Fallback na import_service
            from services.import_service import get_import_service
            svc = get_import_service()
            result = svc.import_file(str(filepath))
            from importers.import_result import ImportResult
            if isinstance(result, ImportResult):
                return result.items
            elif isinstance(result, list):
                return result
            return []

