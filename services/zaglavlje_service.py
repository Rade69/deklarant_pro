# services/zaglavlje_service.py

"""
Zaglavlje Service - Business Logic Layer

Service za upravljanje podacima zaglavlja deklaracije.
Potpuno nezavisan od Qt framework-a.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path
import xml.etree.ElementTree as ET
import math

from database.db import get_db_connection
from services.exceptions import ValidationError
from core.draft.draft import DeclarationDraft, AttachedDocument, NaimenovanjeDraft


logger = logging.getLogger("asycuda_pro.services.zaglavlje")


class ZaglavljeService:
    """
    Business logic za zaglavlje deklaracije.

    Odgovornosti:
    - Validacija podataka zaglavlja
    - Čuvanje/učitavanje iz baze
    - XML import/export
    - Data transformacije
    - Draft integracija

    Nema Qt zavisnosti (bez QWidget, Signal, itd.)
    """

    def __init__(self):
        self.logger = logger

    def _log_operation(self, message: str, success: bool = True):
        """Helper za logovanje operacija."""
        if success:
            self.logger.info(f"✅ {message}")
        else:
            self.logger.error(f"❌ {message}")
    
    # ============================================================
    # PUBLIC METHODS
    # ============================================================
    
    def save_zaglavlje(self, data: Dict[str, Any]) -> bool:
        """
        Sačuvaj zaglavlje u bazu.
        
        Args:
            data: Dictionary sa podacima zaglavlja
        
        Returns:
            True ako je uspješno
        
        Raises:
            ValidationError: Ako podaci nisu validni
        """
        # 1. Validacija
        self._validate(data)
        
        # 2. Database operacije
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO zaglavlje (
                            broj_deklaracije, datum, vrsta_deklaracije,
                            tip_postupka, izvoznik_id, primalac_id,
                            deklarant_id, vid_unutra, obrazac_1, obrazac_2,
                            stavke_broj, created_at, updated_at
                        ) VALUES (
                            %(broj_deklaracije)s, %(datum)s, %(vrsta_deklaracije)s,
                            %(tip_postupka)s, %(izvoznik_id)s, %(primalac_id)s,
                            %(deklarant_id)s, %(vid_unutra)s, %(obrazac_1)s,
                            %(obrazac_2)s, %(stavke_broj)s, NOW(), NOW()
                        )
                        ON CONFLICT (broj_deklaracije) DO UPDATE SET
                            datum = EXCLUDED.datum,
                            vrsta_deklaracije = EXCLUDED.vrsta_deklaracije,
                            tip_postupka = EXCLUDED.tip_postupka,
                            izvoznik_id = EXCLUDED.izvoznik_id,
                            primalac_id = EXCLUDED.primalac_id,
                            deklarant_id = EXCLUDED.deklarant_id,
                            vid_unutra = EXCLUDED.vid_unutra,
                            obrazac_1 = EXCLUDED.obrazac_1,
                            obrazac_2 = EXCLUDED.obrazac_2,
                            stavke_broj = EXCLUDED.stavke_broj,
                            updated_at = NOW()
                    """, data)
            
            self.logger.info(f"Zaglavlje sačuvano: {data.get('broj_deklaracije')}")
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri čuvanju zaglavlja: {e}")
            raise
    
    def load_zaglavlje(self, broj_deklaracije: str) -> Optional[Dict[str, Any]]:
        """
        Učitaj zaglavlje iz baze.
        
        Args:
            broj_deklaracije: Broj deklaracije za učitavanje
        
        Returns:
            Dictionary sa podacima ili None ako ne postoji
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT * FROM zaglavlje
                        WHERE broj_deklaracije = %s
                        LIMIT 1
                    """, (broj_deklaracije,))
                    
                    row = cur.fetchone()
                    if row:
                        return dict(row)
                    return None
                    
        except Exception as e:
            self.logger.error(f"Greška pri učitavanju zaglavlja: {e}")
            return None
    
    def delete_zaglavlje(self, broj_deklaracije: str) -> bool:
        """
        Obriši zaglavlje iz baze.
        
        Args:
            broj_deklaracije: Broj deklaracije za brisanje
        
        Returns:
            True ako je uspješno, False ako ne postoji
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        DELETE FROM zaglavlje
                        WHERE broj_deklaracije = %s
                    """, (broj_deklaracije,))
                    
                    deleted = cur.rowcount > 0
                    
                    if deleted:
                        self.logger.info(f"Zaglavlje obrisano: {broj_deklaracije}")
                    else:
                        self.logger.warning(f"Zaglavlje ne postoji: {broj_deklaracije}")
                    
                    return deleted
                    
        except Exception as e:
            self.logger.error(f"Greška pri brisanju zaglavlja: {e}")
            return False
    
    def load_from_xml(self, filepath: str, format_type: str = "world") -> Dict[str, Any]:
        """
        Učitaj zaglavlje iz XML fajla.
        
        Args:
            filepath: Putanja do XML fajla
            format_type: Tip formata - "world" ili "pro" (default: "world")
        
        Returns:
            Dictionary sa podacima zaglavlja
        
        Raises:
            FileNotFoundError: Ako fajl ne postoji
            ValueError: Ako XML format nije validan
        """
        filepath = Path(filepath)
        
        if not filepath.exists():
            raise FileNotFoundError(f"XML fajl ne postoji: {filepath}")
        
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
            
            if format_type.lower() == "pro":
                return self._parse_pro_xml(root)
            else:
                return self._parse_xml(root)
            
        except ET.ParseError as e:
            raise ValueError(f"Neispravan XML format: {e}")
    
    def _parse_pro_xml(self, root: ET.Element) -> Dict[str, Any]:
        """
        Parsira ASYCUDA Pro XML strukturu.
        
        Args:
            root: Root XML element
        
        Returns:
            Dictionary sa podacima zaglavlja
        """
        data = {}
        
        # Namespace handling
        ns = {}
        if root.tag.startswith('{'):
            uri = root.tag.split('}')[0][1:]
            ns['ns'] = uri
        
        def find_with_ns(parent, tag):
            if ns:
                result = parent.find(f"ns:{tag}", ns)
                if result is not None:
                    return result
            return parent.find(tag)
        
        # Osnovni podaci
        decl_number = find_with_ns(root, 'DeclarationNumber')
        if decl_number is not None and decl_number.text:
            data['broj_deklaracije'] = decl_number.text.strip()
        
        decl_date = find_with_ns(root, 'DeclarationDate')
        if decl_date is not None and decl_date.text:
            data['datum'] = decl_date.text.strip()
        
        decl_type = find_with_ns(root, 'DeclarationType')
        if decl_type is not None and decl_type.text:
            data['vrsta_deklaracije'] = decl_type.text.strip()
        
        # Izvoznik
        exporter = find_with_ns(root, 'Exporter')
        if exporter is not None:
            data['izvoznik_id'] = self._get_text_from_element(exporter, ['ID', 'Code'])
            data['izvoznik_naziv'] = self._get_text_from_element(exporter, ['Name', 'CompanyName'])
        
        # Primalac
        consignee = find_with_ns(root, 'Consignee')
        if consignee is not None:
            data['primalac_id'] = self._get_text_from_element(consignee, ['ID', 'Code'])
            data['primalac_naziv'] = self._get_text_from_element(consignee, ['Name', 'CompanyName'])
        
        # Transport
        transport = find_with_ns(root, 'TransportMeans')
        if transport is not None:
            data['transport_id'] = self._get_text_from_element(transport, ['ID', 'Number'])
            data['aktivno_transport'] = self._get_text_from_element(transport, ['Nationality', 'Country'])

        # ── Priložene isprave (Attached_documents) iz Item sekcija ─────────────
        data['attached_documents'] = []
        seen_docs = set()
        ns_pro = {'n': root.tag.split('}')[0][1:]} if root.tag.startswith('{') else {}
        tag_prefix = f"{{{root.tag.split('}')[0][1:]}}}Item" if ns_pro else "Item"
        attached_tag_prefix = f"{{{root.tag.split('}')[0][1:]}}}Attached_documents" if ns_pro else "Attached_documents"
        code_tag = f"{{{root.tag.split('}')[0][1:]}}}Attached_document_code" if ns_pro else "Attached_document_code"
        name_tag = f"{{{root.tag.split('}')[0][1:]}}}Attached_document_name" if ns_pro else "Attached_document_name"
        ref_tag = f"{{{root.tag.split('}')[0][1:]}}}Attached_document_reference" if ns_pro else "Attached_document_reference"
        from_rule_tag = f"{{{root.tag.split('}')[0][1:]}}}Attached_document_from_rule" if ns_pro else "Attached_document_from_rule"

        for item_el in root.iter(tag_prefix):
            for att_el in item_el.iter(attached_tag_prefix):
                code_el = att_el.find(code_tag)
                name_el = att_el.find(name_tag)
                ref_el = att_el.find(ref_tag)
                from_rule_el = att_el.find(from_rule_tag)
                code = code_el.text.strip() if code_el is not None and code_el.text else ''
                name = name_el.text.strip() if name_el is not None and name_el.text else ''
                ref = ref_el.text.strip() if ref_el is not None and ref_el.text else ''
                from_rule = True  # Svaki upisani dokument je fizički priložen
                doc_key = (code, ref)
                if doc_key not in seen_docs and code:
                    seen_docs.add(doc_key)
                    data['attached_documents'].append({
                        'code': code,
                        'name': name,
                        'number': ref,
                        'from_rule': from_rule,
                    })

        return data
    
    def _get_text_from_element(self, element: ET.Element, tag_variants: List[str]) -> str:
        """Pomoćna funkcija za dobijanje teksta iz elementa sa više mogućih tagova."""
        for tag in tag_variants:
            found = element.find(tag)
            if found is not None and found.text:
                return found.text.strip()
        return ""
    
    def export_to_xml(self, data: Dict[str, Any], filepath: str, format_type: str = "world") -> bool:
        """
        Eksportuj zaglavlje u XML fajl.
        
        Args:
            data: Podaci zaglavlja
            filepath: Putanja do XML fajla
            format_type: Tip formata - "world" ili "pro" (default: "world")
        
        Returns:
            True ako je uspješno
        """
        try:
            root = self._build_xml(data, format_type)
            tree = ET.ElementTree(root)
            tree.write(filepath, encoding='utf-8', xml_declaration=True)
            
            self.logger.info(f"XML eksportovan ({format_type}): {filepath}")
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri XML eksportu ({format_type}): {e}")
            return False
    
    def get_vrste_deklaracija(self) -> Dict[str, List[tuple[str, str]]]:
        """
        Dohvati vrste deklaracija iz baze.
        
        Returns:
            Dictionary {sifra: [(oznaka, opis), ...]}
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT sifra, oznaka, opis
                        FROM catalogs.vrste_deklaracija
                        ORDER BY sifra, oznaka
                    """)
                    
                    result: Dict[str, List[tuple[str, str]]] = {}
                    for row in cur.fetchall():
                        sifra = row['sifra']
                        if sifra not in result:
                            result[sifra] = []
                        result[sifra].append((row['oznaka'], row['opis']))
                    
                    return result
                    
        except Exception as e:
            self.logger.error(f"Greška pri učitavanju vrsta deklaracija: {e}")
            return {}
    
    def get_tipovi_deklaracija(self) -> List[tuple[str, str]]:
        """
        Dohvati tipove deklaracija iz baze.
        
        Returns:
            Lista [(sifra, opis), ...]
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT sifra, opis
                        FROM catalogs.tipovi_deklaracija
                        ORDER BY sifra
                    """)
                    
                    return [(row['sifra'], row['opis']) for row in cur.fetchall()]
                    
        except Exception as e:
            self.logger.error(f"Greška pri učitavanju tipova deklaracija: {e}")
            return []
    
    def get_vid_unutra(self) -> List[tuple[str, str]]:
        """
        Dohvati vidove unutra iz baze.
        
        Returns:
            Lista [(sifra, opis), ...]
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT sifra, opis
                        FROM catalogs.vid_unutra
                        ORDER BY sifra
                    """)
                    
                    return [(row['sifra'], row['opis']) for row in cur.fetchall()]
                    
        except Exception as e:
            self.logger.error(f"Greška pri učitavanju vid unutra: {e}")
            return []

    def load_vrste_prijevoza(self) -> List[Dict[str, Any]]:
        """
        Učitaj vrste prijevoza iz baze.

        Returns:
            Lista dict-ova sa poljima: sifra, naziv

        Primjer:
            >>> service.load_vrste_prijevoza()
            [{'sifra': '1', 'naziv': 'Pomorski'}, {'sifra': '2', 'naziv': 'Željeznički'}]
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT sifra, opis
                        FROM catalogs.vrste_prijevoza
                        ORDER BY sifra
                    """)
                    results = [dict(row) for row in cur.fetchall()]
                    self._log_operation(f"load_vrste_prijevoza: {len(results)} records")
                    return results
        except Exception as e:
            self._log_operation("load_vrste_prijevoza", success=False)
            self.logger.error(f"Greška pri učitavanju vrste prijevoza: {e}")
            return []

    def load_ured_odredista(self) -> str:
        """
        Učitaj ured odredišta iz baze (carinska ispostava sa sifra='BA097012').

        Returns:
            Formatirani string: "BA097012 CI Grad"

        Primjer:
            >>> service.load_ured_odredista()
            'BA097012 CI Bijeljina'
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT sifra, naziv
                        FROM catalogs.carinske_ispostave
                        WHERE sifra = 'BA097012'
                    """)
                    row = cur.fetchone()
                    if row:
                        # Ekstraktuj grad iz naziva: "6. Carinska ispostava Bijeljina" → "Bijeljina"
                        grad = row["naziv"].split()[-1]
                        result = f"{row['sifra']} CI {grad}"
                        self._log_operation(f"load_ured_odredista: {result}")
                        return result
            self._log_operation("load_ured_odredista: not found")
            return ""
        except Exception as e:
            self._log_operation("load_ured_odredista", success=False)
            self.logger.error(f"Greška pri učitavanju ured odredišta: {e}")
            return ""

    def load_isprave(self) -> Dict[str, str]:
        """
        Učitaj šifre i nazive isprava iz baze.

        Returns:
            Dictionary {sifra: naziv}

        Primjer:
            >>> service.load_isprave()
            {'N380': 'T1 deklaracija', 'T2L': 'T2L isprava'}
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT sifra, opis
                        FROM catalogs.prilozeni_dokumenti_sifre
                        ORDER BY sifra
                    """)
                    rows = cur.fetchall()
                    result = {row['sifra']: row['opis'] for row in rows}
                    self._log_operation(f"load_isprave: {len(result)} records")
                    return result
        except Exception as e:
            self._log_operation("load_isprave", success=False)
            self.logger.error(f"Greška pri učitavanju isprava: {e}")
            return {}

    # ============================================================
    # DRAFT INTEGRATION METHODS
    # ============================================================

    def load_from_draft(self, draft: DeclarationDraft) -> Dict[str, Any]:
        """
        Učitaj podatke iz DeclarationDraft objekta.

        Ekstraktuje SVA zaglavlje polja iz Draft-a i transformiše ih
        u format koji View očekuje (get_data format).

        Args:
            draft: DeclarationDraft objekat sa podacima

        Returns:
            Dictionary sa podacima spremnim za View

        Mapping:
            - draft.broj_deklaracije → data['broj_deklaracije']
            - draft.datum_prijema → data['datum_prijema']
            - draft.vrsta_deklaracije → data['vrsta_deklaracije']
            - ... svih 40+ polja
        """
        data = {}

        # Rubrika 1 - Deklaracija
        data['deklaracija_1'] = getattr(draft, 'deklaracija_tip', '') or ''
        data['deklaracija_a'] = getattr(draft, 'deklaracija_a', '') or ''
        data['deklaracija_oznaka'] = getattr(draft, 'deklaracija_oznaka', '') or ''

        # Rubrika 2 - Izvoznik
        data['izvoznik_id'] = getattr(draft, 'izvoznik_id', '') or ''
        data['izvoznik_r1'] = getattr(draft, 'izvoznik_naziv', '') or ''
        data['izvoznik_r2'] = getattr(draft, 'izvoznik_adresa', '') or ''
        data['izvoznik_r3'] = getattr(draft, 'izvoznik_grad', '') or ''
        data['izvoznik_r4'] = getattr(draft, 'izvoznik_postanski_broj', '') or ''
        data['izvoznik_r5'] = getattr(draft, 'izvoznik_drzava', '') or ''

        # Rubrika 8 - Primalac
        data['primalac_id'] = getattr(draft, 'primalac_id', '') or ''
        data['primalac_r1'] = getattr(draft, 'primalac_naziv', '') or ''
        data['primalac_r2'] = getattr(draft, 'primalac_adresa', '') or ''
        data['primalac_r3'] = getattr(draft, 'primalac_grad', '') or ''
        data['primalac_r4'] = getattr(draft, 'primalac_postanski_broj', '') or ''
        data['primalac_r5'] = getattr(draft, 'primalac_drzava', '') or ''

        # Rubrika 14 - Deklarant
        data['deklarant_id'] = getattr(draft, 'deklarant_id', '') or ''
        data['deklarant_r1'] = getattr(draft, 'deklarant_naziv', '') or ''
        data['deklarant_r2'] = getattr(draft, 'deklarant_adresa', '') or ''
        data['deklarant_r3'] = getattr(draft, 'deklarant_grad', '') or ''
        data['deklarant_r4'] = getattr(draft, 'deklarant_postanski_broj', '') or ''
        data['deklarant_r5'] = getattr(draft, 'deklarant_drzava', '') or ''

        # Rubrika 18/19 - Transport
        data['transport_id'] = getattr(draft, 'transport_id', '') or ''
        data['kontejner'] = bool(getattr(draft, 'kontejner', False))

        # Rubrika 18 - nacionalnost pri polasku
        data['transport_nacionalnost'] = getattr(draft, 'transport_nacionalnost', '') or ''
        # Rubrika 19 - kontejner broj
        data['kontejner_broj'] = getattr(draft, 'kontejner_broj', '') or ''
        # Rubrika 21 - aktivno transp. + nacionalnost na granici
        data['aktivno_transport'] = getattr(draft, 'aktivno_transport', '') or ''
        data['aktivno_transport_nat'] = getattr(draft, 'aktivno_transport_nat', '') or ''

        # Rubrika 25, 26, 27 - Vid unutra/granica/mjesto otvarač
        data['vid_25'] = getattr(draft, 'vid_unutra', '') or ''
        data['vid_26'] = getattr(draft, 'vid_granica', '') or ''
        data['vid_27'] = getattr(draft, 'mjesto_otvaraca', '') or ''

        # Rubrika 29 - Izlazna carinarnica
        data['izlazna_carinarnica'] = getattr(draft, 'izlazna_carinarnica', '') or ''

        # Rubrika 30 - Lokacija robe
        data['lokacija_robe'] = getattr(draft, 'lokacija_robe', '') or ''

        # Rubrika 3 - Obrasci
        data['obrazac_1'] = getattr(draft, 'obrazac_1', '') or ''
        data['obrazac_2'] = getattr(draft, 'obrazac_2', '') or ''

        # Rubrika 4 - Tovarni listovi
        data['tovarni_listovi'] = getattr(draft, 'tovarni_listovi', '') or ''

        # Rubrika 5 - Stavke (auto-kalkulacija)
        n_items = len(draft.items) if hasattr(draft, 'items') and draft.items else 0
        data['stavke'] = str(n_items)
        if n_items > 0:
            data['obrazac_1'] = '1'
            data['obrazac_2'] = str(math.ceil(n_items / 3))

        # Rubrika 6 - Uk. paketa
        data['uk_paketa'] = getattr(draft, 'uk_paketa', '') or ''

        # Rubrika 7 - Ref.br.
        data['ref_br'] = getattr(draft, 'ref_br', '') or ''

        # Rubrika 9 - Odgovorna zemlja
        data['odg_zemlja_1'] = getattr(draft, 'odg_zemlja_1', '') or ''
        data['odg_zemlja_2'] = getattr(draft, 'odg_zemlja_2', '') or ''
        data['odg_zemlja_3'] = getattr(draft, 'odg_zemlja_3', '') or ''
        data['odg_zemlja_4'] = getattr(draft, 'odg_zemlja_4', '') or ''

        # Rubrika 10, 11, 12, 13 - Zemlje
        data['zem_10'] = getattr(draft, 'zem_10', '') or ''
        data['zem_11'] = getattr(draft, 'zem_11', '') or ''
        data['zem_12'] = getattr(draft, 'zem_12', '') or ''
        data['zem_13'] = getattr(draft, 'zem_13', '') or ''

        # Rubrika 15 - Država izvoza
        data['drzava_izvoza_naziv'] = getattr(draft, 'drzava_izvoza_naziv', '') or ''
        data['drzava_izvoza_sifra'] = getattr(draft, 'drzava_izvoza_sifra', '') or ''

        # Rubrika 16 - Država porijekla
        data['drzava_porijekla'] = getattr(draft, 'drzava_porijekla', '') or ''

        # Rubrika 17 - Država odredišta
        data['drzava_odredista_naziv'] = getattr(draft, 'drzava_odredista_naziv', '') or ''
        data['drzava_odredista_sifra'] = getattr(draft, 'drzava_odredista_sifra', '') or ''

        # Rubrika 20 - Uslovi isporuke
        data['uslovi_kod'] = getattr(draft, 'uslovi_kod', '') or ''
        data['uslovi_mjesto'] = getattr(draft, 'uslovi_mjesto', '') or ''

        # Rubrika 22, 23, 24 - Valuta, iznos, kurs
        # invoice_lines uvijek imaju prioritet — XML može sadržavati zastarjeli iznos
        invoice_lines = getattr(draft, 'invoice_lines', None) or []
        iznos_iz_fakture = sum(getattr(l, 'iznos', 0.0) or 0.0 for l in invoice_lines)
        if iznos_iz_fakture:
            iznos_val = iznos_iz_fakture
            draft.iznos = iznos_val
        else:
            iznos_val = getattr(draft, 'iznos', 0.0) or 0.0
        valuta = getattr(draft, 'valuta', '') or ''
        if not valuta:
            for l in invoice_lines:
                v = getattr(l, 'valuta', '') or ''
                if v:
                    valuta = v
                    draft.valuta = valuta
                    break
        data['valuta'] = valuta
        data['iznos'] = f"{iznos_val:.2f}" if iznos_val else ''
        kurs_val = getattr(draft, 'kurs', 1.0) or 1.0
        data['kurs'] = str(kurs_val) if kurs_val != 1.0 else ''
        data['vrsta_trans_1'] = getattr(draft, 'vrsta_trans_1', '') or ''
        data['vrsta_trans_2'] = getattr(draft, 'vrsta_trans_2', '') or ''

        # Troškovi transporta (Rb. 20 okvir)
        for i in range(1, 6):
            data[f'trosak_{i}'] = getattr(draft, f'trosak_{i}', '0,00') or '0,00'

        # Rubrika 40 - Zbirna deklaracija / prethodni dokument
        data['rb40_tip'] = getattr(draft, 'rb40_tip', '') or ''
        data['rb40_skracenica'] = getattr(draft, 'rb40_skracenica', '') or ''
        data['rb40_broj'] = getattr(draft, 'rb40_broj', '') or ''

        # Rubrika 48, 49 - Odgođeno plaćanje / identifikacija skladišta
        data['odgodjeno_placanje'] = getattr(draft, 'odgodjeno_placanje', '') or ''
        data['identifikacija_skladista'] = getattr(draft, 'identifikacija_skladista', '') or ''

        # Priložene isprave (header_attached_documents)
        data['attached_documents'] = []
        if hasattr(draft, 'header_attached_documents') and draft.header_attached_documents:
            for doc in draft.header_attached_documents:
                data['attached_documents'].append({
                    'code': getattr(doc, 'code', ''),
                    'name': getattr(doc, 'name', ''),
                    'number': getattr(doc, 'number', ''),
                    'from_rule': True,  # Svaki upisani dokument je fizički priložen
                })

        self._log_operation(f"Učitavanje iz Draft-a: {getattr(draft, 'broj_deklaracije', 'N/A')}")

        return data

    def save_to_draft(
        self,
        draft: DeclarationDraft,
        data: Dict[str, Any]
    ) -> DeclarationDraft:
        """
        Sačuvaj podatke u DeclarationDraft objekat.

        Uzima podatke iz View (get_data format) i upisuje ih u
        odgovarajuća polja DeclarationDraft objekta.

        Args:
            draft: DeclarationDraft objekat za upis
            data: Podaci iz View (get_data format)

        Returns:
            Ažurirani DeclarationDraft objekat

        Mapping:
            - data['broj_deklaracije'] → draft.broj_deklaracije
            - data['datum_prijema'] → draft.datum_prijema
            - ... svih 40+ polja
        """

        def safe_get(key: str, default: Any = '') -> Any:
            """Helper za sigurno dohvaćanje vrijednosti iz data dict."""
            value = data.get(key, default)
            return value if value is not None else default

        def safe_float(key: str, default: float = 0.0) -> float:
            """Helper za konverziju string → float (EU i US format)."""
            raw = data.get(key, '')
            if raw is None or raw == '':
                return default
            try:
                # EU format: zamijeni zarez tačkom, ukloni tačku hiljadaricu
                cleaned = str(raw).replace(',', '.')
                return float(cleaned)
            except (ValueError, TypeError):
                return default

        # Rubrika 1 - Deklaracija
        draft.deklaracija_tip = safe_get('deklaracija_1')
        draft.deklaracija_a = safe_get('deklaracija_a')
        draft.deklaracija_oznaka = safe_get('deklaracija_oznaka')

        # Rubrika 2 - Izvoznik
        draft.izvoznik_id = safe_get('izvoznik_id')
        draft.izvoznik_naziv = safe_get('izvoznik_r1')
        draft.izvoznik_adresa = safe_get('izvoznik_r2')
        draft.izvoznik_grad = safe_get('izvoznik_r3')
        draft.izvoznik_postanski_broj = safe_get('izvoznik_r4')
        draft.izvoznik_drzava = safe_get('izvoznik_r5')

        # Rubrika 8 - Primalac
        draft.primalac_id = safe_get('primalac_id')
        draft.primalac_naziv = safe_get('primalac_r1')
        draft.primalac_adresa = safe_get('primalac_r2')
        draft.primalac_grad = safe_get('primalac_r3')
        draft.primalac_postanski_broj = safe_get('primalac_r4')
        draft.primalac_drzava = safe_get('primalac_r5')

        # Rubrika 14 - Deklarant
        draft.deklarant_id = safe_get('deklarant_id')
        draft.deklarant_naziv = safe_get('deklarant_r1')
        draft.deklarant_adresa = safe_get('deklarant_r2')
        draft.deklarant_grad = safe_get('deklarant_r3')
        draft.deklarant_postanski_broj = safe_get('deklarant_r4')
        draft.deklarant_drzava = safe_get('deklarant_r5')

        # Rubrika 18/19 - Transport
        draft.transport_id = safe_get('transport_id')
        draft.kontejner = bool(data.get('kontejner', False))

        # Rubrika 18 - nacionalnost pri polasku
        draft.transport_nacionalnost = safe_get('transport_nacionalnost')
        # Rubrika 19 - kontejner broj
        draft.kontejner_broj = safe_get('kontejner_broj')
        # Rubrika 21 - Aktivno transportno sredstvo + nacionalnost na granici
        draft.aktivno_transport = safe_get('aktivno_transport')
        draft.aktivno_transport_nat = safe_get('aktivno_transport_nat')

        # Rubrika 25, 26, 27 - Vid unutra/granica/mjesto otvarač
        draft.vid_unutra = safe_get('vid_25')
        draft.vid_granica = safe_get('vid_26')
        draft.mjesto_otvaraca = safe_get('vid_27')

        # Rubrika 29 - Izlazna carinarnica
        draft.izlazna_carinarnica = safe_get('izlazna_carinarnica')

        # Rubrika 30 - Lokacija robe
        draft.lokacija_robe = safe_get('lokacija_robe')

        # Rubrika 3 - Obrasci
        draft.obrazac_1 = safe_get('obrazac_1')
        draft.obrazac_2 = safe_get('obrazac_2')

        # Rubrika 4 - Tovarni listovi
        draft.tovarni_listovi = safe_get('tovarni_listovi')

        # Rubrika 5 - Stavke (items se upravljaju van ovog taba)

        # Rubrika 6 - Uk. paketa
        draft.uk_paketa = safe_get('uk_paketa')

        # Rubrika 7 - Ref.br.
        draft.ref_br = safe_get('ref_br')

        # Rubrika 9 - Odgovorna zemlja
        draft.odg_zemlja_1 = safe_get('odg_zemlja_1')
        draft.odg_zemlja_2 = safe_get('odg_zemlja_2')
        draft.odg_zemlja_3 = safe_get('odg_zemlja_3')
        draft.odg_zemlja_4 = safe_get('odg_zemlja_4')

        # Rubrika 10, 11, 12, 13 - Zemlje
        draft.zem_10 = safe_get('zem_10')
        draft.zem_11 = safe_get('zem_11')
        draft.zem_12 = safe_get('zem_12')
        draft.zem_13 = safe_get('zem_13')

        # Rubrika 15 - Država izvoza
        draft.drzava_izvoza_naziv = safe_get('drzava_izvoza_naziv')
        draft.drzava_izvoza_sifra = safe_get('drzava_izvoza_sifra')

        # Rubrika 16 - Država porijekla
        draft.drzava_porijekla = safe_get('drzava_porijekla')

        # Rubrika 17 - Država odredišta
        draft.drzava_odredista_naziv = safe_get('drzava_odredista_naziv')
        draft.drzava_odredista_sifra = safe_get('drzava_odredista_sifra')

        # Rubrika 20 - Uslovi isporuke
        draft.uslovi_kod = safe_get('uslovi_kod')
        draft.uslovi_mjesto = safe_get('uslovi_mjesto')

        # Rubrika 22, 23, 24 - Valuta, iznos, kurs
        draft.valuta = safe_get('valuta')
        draft.iznos = safe_float('iznos', 0.0)
        draft.kurs = safe_float('kurs', 1.0) or 1.0
        draft.vrsta_trans_1 = safe_get('vrsta_trans_1')
        draft.vrsta_trans_2 = safe_get('vrsta_trans_2')

        # Troškovi transporta
        for i in range(1, 6):
            setattr(draft, f'trosak_{i}', safe_get(f'trosak_{i}', '0,00'))

        # Rubrika 40 - Zbirna deklaracija / prethodni dokument
        draft.rb40_tip = safe_get('rb40_tip')
        draft.rb40_skracenica = safe_get('rb40_skracenica')
        draft.rb40_broj = safe_get('rb40_broj')

        # Rubrika 48, 49 - Odgođeno plaćanje / identifikacija skladišta
        draft.odgodjeno_placanje = safe_get('odgodjeno_placanje')
        draft.identifikacija_skladista = safe_get('identifikacija_skladista')

        # Priložene isprave (header_attached_documents)
        if 'attached_documents' in data and data['attached_documents']:
            draft.header_attached_documents = []
            for doc in data['attached_documents']:
                if isinstance(doc, dict) and doc.get('code'):
                    draft.header_attached_documents.append(
                        AttachedDocument(
                            code=doc.get('code', ''),
                            name=doc.get('name', ''),
                            number=doc.get('number', ''),
                            from_rule=doc.get('from_rule', False),
                        )
                    )
        elif 'attached_documents' in data:
            # Eksplicitno prazna lista — očisti
            draft.header_attached_documents = []

        self._log_operation(f"Čuvanje u Draft: {getattr(draft, 'broj_deklaracije', 'N/A')}")

        return draft

    # ============================================================
    # PRIVATE METHODS - VALIDATION
    # ============================================================
    
    def _validate(self, data: Dict[str, Any]) -> None:
        """
        Validiraj podatke zaglavlja.
        
        Raises:
            ValidationError: Ako validacija ne prođe
        """
        # Obavezna polja
        required_fields = [
            'broj_deklaracije',
            'datum',
        ]
        
        for field in required_fields:
            if not data.get(field):
                raise ValidationError(f"Polje '{field}' je obavezno", field=field)
        
        # Validacija formata broja deklaracije
        broj = data.get('broj_deklaracije', '')
        if not isinstance(broj, str) or len(broj.strip()) == 0:
            raise ValidationError("Broj deklaracije mora biti string", field='broj_deklaracije')
        
        # Validacija datuma
        datum = data.get('datum')
        if datum and not isinstance(datum, (datetime, str)):
            raise ValidationError("Datum mora biti datetime ili string", field='datum')
    
    # ============================================================
    # PRIVATE METHODS - XML PARSING
    # ============================================================
    
    def _parse_xml(self, root: ET.Element) -> Dict[str, Any]:
        """
        Parsira ASYCUDA XML strukturu (format generisan od AsycudaXMLBuilder).

        Root: <ASYCUDA>
          <Property><Forms>, <Nbers>
          <Identification><Type>
          <Traders><Exporter>, <Consignee>
          <Declarant>
          <General_information><Country>
          <Transport><Means_of_transport>, <Delivery_terms>, <Border_office>, ...
          <Financial><Financial_transaction>, <Deffered_payment_reference>
          <Warehouse><Identification>
          <Valuation><Gs_external_freight>, <Gs_insurance>, ...

        Args:
            root: Root XML element (<ASYCUDA>)

        Returns:
            Dictionary sa podacima u view formatu
        """
        data = {}

        # Helper: namespace-aware find
        ns: Dict[str, str] = {}
        if root.tag.startswith('{'):
            uri = root.tag.split('}')[0][1:]
            ns['n'] = uri

        def _find(parent: ET.Element, tag: str) -> Optional[ET.Element]:
            if ns:
                el = parent.find(f"n:{tag}", ns)
                if el is not None:
                    return el
            return parent.find(tag)

        def _txt(parent: ET.Element, tag: str) -> str:
            el = _find(parent, tag)
            if el is not None and el.text:
                return el.text.strip()
            return ""

        def _multiline(name: str, r1: str, r3: str, r2: str) -> None:
            """Parsiraj multi-line party name → r1 (naziv), r3 (grad), r2 (adresa)."""
            lines = [l.strip() for l in name.split('\n') if l.strip()]
            data[r1] = lines[0] if len(lines) > 0 else ''
            data[r3] = lines[1] if len(lines) > 1 else ''
            data[r2] = lines[2] if len(lines) > 2 else ''

        # ── Rb. 4: Tovarni listovi ────────────────────────────────────────
        prop = _find(root, "Property")
        if prop is not None:
            nbers = _find(prop, "Nbers")
            if nbers is not None:
                data['tovarni_listovi'] = _txt(nbers, "Number_of_loading_lists")

        # ── Rb. 1: Tip deklaracije ────────────────────────────────────────────
        ident = _find(root, "Identification")
        if ident is not None:
            type_el = _find(ident, "Type")
            if type_el is not None:
                data['deklaracija_1'] = _txt(type_el, "Type_of_declaration")
                data['deklaracija_a'] = _txt(type_el, "Type_of_Declaration_X")
                data['deklaracija_oznaka'] = _txt(type_el, "Declaration_gen_procedure_code")

        # ── Rb. 2: Izvoznik i Rb. 8: Primalac ────────────────────────────────
        traders = _find(root, "Traders")
        if traders is not None:
            exp_el = _find(traders, "Exporter")
            if exp_el is not None:
                data['izvoznik_id'] = _txt(exp_el, "Exporter_code")
                exp_name = _txt(exp_el, "Exporter_name")
                if exp_name:
                    _multiline(exp_name, 'izvoznik_r1', 'izvoznik_r3', 'izvoznik_r5')

            cons_el = _find(traders, "Consignee")
            if cons_el is not None:
                data['primalac_id'] = _txt(cons_el, "Consignee_code")
                cons_name = _txt(cons_el, "Consignee_name")
                if cons_name:
                    _multiline(cons_name, 'primalac_r1', 'primalac_r3', 'primalac_r2')

        # ── Rb. 14: Deklarant ──────────────────────────────────────────────────
        decl_el = _find(root, "Declarant")
        if decl_el is not None:
            data['deklarant_id'] = _txt(decl_el, "Declarant_code")
            decl_name = _txt(decl_el, "Declarant_name")
            if decl_name:
                _multiline(decl_name, 'deklarant_r1', 'deklarant_r3', 'deklarant_r2')
            ref_el = _find(decl_el, "Reference")
            if ref_el is not None:
                data['ref_br'] = _txt(ref_el, "Number")

        # ── Rb. 15, 16, 17: Države ────────────────────────────────────────────
        gen_info = _find(root, "General_information")
        if gen_info is not None:
            country_el = _find(gen_info, "Country")
            if country_el is not None:
                export_el = _find(country_el, "Export")
                if export_el is not None:
                    data['drzava_izvoza_sifra'] = _txt(export_el, "Export_country_code")
                    data['drzava_izvoza_naziv'] = _txt(export_el, "Export_country_name")
                dest_el = _find(country_el, "Destination")
                if dest_el is not None:
                    data['drzava_odredista_sifra'] = _txt(dest_el, "Destination_country_code")
                    data['drzava_odredista_naziv'] = _txt(dest_el, "Destination_country_name")
            data['drzava_porijekla'] = _txt(gen_info, "Country_of_origin_name")

        # ── Rb. 19, 20, 25, 26, 29, 30 ───────────────────────────────
        transport_el = _find(root, "Transport")
        if transport_el is not None:
            means = _find(transport_el, "Means_of_transport")
            if means is not None:
                border_info = _find(means, "Border_information")
                if border_info is not None:
                    data['vid_25'] = _txt(border_info, "Mode")
                data['vid_26'] = _txt(means, "Inland_mode_of_transport")

            container_flag = _txt(transport_el, "Container_flag")
            data['kontejner'] = (container_flag.lower() == "true")

            delivery = _find(transport_el, "Delivery_terms")
            if delivery is not None:
                data['uslovi_kod'] = _txt(delivery, "Code")
                data['uslovi_mjesto'] = _txt(delivery, "Place")

            border_office = _find(transport_el, "Border_office")
            if border_office is not None:
                code = _txt(border_office, "Code")
                name = _txt(border_office, "Name")
                data['izlazna_carinarnica'] = f"{code} - {name}".strip(" -") if name else code

            data['lokacija_robe'] = _txt(transport_el, "Location_of_goods")

        # ── Rb. 22, 23, 24: Vrsta finansijske transakcije ─────────────────────
        financial = _find(root, "Financial")
        if financial is not None:
            fin_trans = _find(financial, "Financial_transaction")
            if fin_trans is not None:
                data['vrsta_trans_1'] = _txt(fin_trans, "code1")
                data['vrsta_trans_2'] = _txt(fin_trans, "code2")

        # ── Rb. 49: Identifikacija skladišta ──────────────────────────────────
        warehouse = _find(root, "Warehouse")
        if warehouse is not None:
            wh_id = _find(warehouse, "Identification")
            if wh_id is not None and wh_id.text:
                data['identifikacija_skladista'] = wh_id.text.strip()

        # ── Troškovi: trosak_1..5 ─────────────────────────────────────────────
        valuation = _find(root, "Valuation")
        if valuation is not None:
            # ── Rb. 22, 23: Valuta, iznos, kurs ─────────────────────────────
            gs_inv = _find(valuation, "Gs_Invoice")
            if gs_inv is not None:
                curr_code = _txt(gs_inv, "Currency_code")
                if curr_code:
                    data['valuta'] = curr_code
                amt = _txt(gs_inv, "Amount_foreign_currency")
                if amt and amt != "0":
                    data['iznos'] = amt
                rate = _txt(gs_inv, "Currency_rate")
                if rate and rate != "1" and rate != "0":
                    data['kurs'] = rate

            # ── Troškovi: trosak_1..5 ─────────────────────────────────────────
            cost_map = {
                'trosak_1': "Gs_external_freight",
                'trosak_2': "Gs_insurance",
                'trosak_3': "Gs_other_cost",
                'trosak_4': "Gs_internal_freight",
                'trosak_5': "Gs_deduction",
            }
            for field, tag in cost_map.items():
                gs = _find(valuation, tag)
                if gs is not None:
                    amt = _txt(gs, "Amount_foreign_currency")
                    if amt and amt != "0":
                        data[field] = amt.replace('.', ',')

        # ── Priložene isprave (Attached_documents) iz Item sekcija ─────────────
        data['attached_documents'] = []
        seen_docs = set()
        items = root.findall("Item")
        if ns:
            items = root.findall(f"n:Item", ns)

        for item_el in items:
            attached_elements = item_el.findall("Attached_documents")
            if ns:
                attached_elements = item_el.findall(f"n:Attached_documents", ns)
            for att_el in attached_elements:
                code = _txt(att_el, "Attached_document_code")
                name = _txt(att_el, "Attached_document_name")
                ref = _txt(att_el, "Attached_document_reference")
                from_rule_str = _txt(att_el, "Attached_document_from_rule")
                from_rule = (from_rule_str == "1")
                # Deduplicate by (code, ref)
                doc_key = (code, ref)
                if doc_key not in seen_docs and code:
                    seen_docs.add(doc_key)
                    data['attached_documents'].append({
                        'code': code,
                        'name': name,
                        'number': ref,
                        'from_rule': from_rule,
                    })

        return data

    def parse_naimenovanja_from_xml(
        self, filepath: str
    ) -> List["NaimenovanjeDraft"]:
        """
        Parsiraj naimenovanja (Item sekcije) iz ASYCUDA XML fajla.

        Ekstrahuje podatke iz svake <Item> sekcije i kreira
        NaimenovanjeDraft objekte.

        Args:
            filepath: Putanja do XML fajla

        Returns:
            Lista NaimenovanjeDraft objekata

        Raises:
            FileNotFoundError: Ako fajl ne postoji
            ValueError: Ako XML nije validan
        """
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"XML fajl ne postoji: {filepath}")

        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
        except ET.ParseError as e:
            raise ValueError(f"Neispravan XML format: {e}")

        ns = {'n': root.tag.split('}')[0][1:]} if root.tag.startswith('{') else {}

        def _find(parent, tag):
            if ns:
                return parent.find(f"n:{tag}", ns)
            return parent.find(tag)

        def _txt(parent, tag):
            el = _find(parent, tag)
            if el is not None and el.text:
                return el.text.strip()
            return ""

        items = []
        item_tag = f"{{{ns.get('n', '')}}}Item" if ns else "Item"

        for ordinal, item_el in enumerate(root.iter(item_tag), start=1):
            item_id = f"xml-import-{ordinal}"

            # ── Rb.31 — Pakovanja i opis robe ────────────────────────
            package_marks = _txt(item_el, "Marks_and_numbers")
            package_qty = _txt(item_el, "Number_of_packages")
            package_code = _txt(item_el, "Kind_of_packages")
            package_name = _txt(item_el, "Kind_of_packages_description")

            # Opis robe — više polja se spaja
            descriptions = []
            for tag in ["Goods_description", "Commercial_description", "Description"]:
                desc = _txt(item_el, tag)
                if desc:
                    descriptions.append(desc)
            goods_description = "\n".join(descriptions) if descriptions else ""

            trade_name = _txt(item_el, "Commercial_name")
            tariff_desc1 = _txt(item_el, "Tariff_description_1")
            tariff_desc2 = _txt(item_el, "Tariff_description_2")

            # Kontejneri
            container_number1 = _txt(item_el, "Container_number")
            container_number2 = ""  # ASYCUDA World obično ima samo jedan

            # ── Rb.33 — Tarifni broj ─────────────────────────────────
            tariff_code = _txt(item_el, "Commodity_code")
            # U nekim formatima je Commodity_code unutar Commodity pod-elementa
            if not tariff_code:
                commodity_el = _find(item_el, "Commodity")
                if commodity_el is not None:
                    tariff_code = _txt(commodity_el, "Code")
            tariff_suffix = _txt(item_el, "Tariff_suffix")

            # ── Rb.34 — Zemlja porijekla ─────────────────────────────
            origin_country_code = _txt(item_el, "Country_of_origin_code")
            origin_country_name = _txt(item_el, "Country_of_origin_name")

            # ── Rb.36 — Povlastica ───────────────────────────────────
            preference_code = _txt(item_el, "Preference_code")
            preference_name = _txt(item_el, "Preference_name")

            # ── Rb.35/38 — Mase ──────────────────────────────────────
            gross_mass_str = _txt(item_el, "Gross_mass")
            net_mass_str = _txt(item_el, "Net_mass")
            try:
                gross_mass_kg = float(gross_mass_str) if gross_mass_str else 0.0
            except ValueError:
                gross_mass_kg = 0.0
            try:
                net_mass_kg = float(net_mass_str) if net_mass_str else 0.0
            except ValueError:
                net_mass_kg = 0.0

            # ── Rb.37 — Procedura ────────────────────────────────────
            procedure_code = _txt(item_el, "Procedure_code")
            procedure_prev_code = _txt(item_el, "Procedure_previous_code")

            # ── Rb.39 — Kvota ────────────────────────────────────────
            quota_code = _txt(item_el, "Quota_order_number")

            # ── Rb.40 — Prethodni dokumenti (tekstualna polja) ───────
            prev_docs = []
            for prev_el in item_el.iter(
                f"{{{ns.get('n', '')}}}Previous_document" if ns else "Previous_document"
            ):
                prev_ref = _txt(prev_el, "Reference")
                if prev_ref:
                    prev_docs.append(prev_ref)
            previous_document = prev_docs[0] if len(prev_docs) > 0 else ""
            previous_document2 = prev_docs[1] if len(prev_docs) > 1 else ""
            previous_document3 = prev_docs[2] if len(prev_docs) > 2 else ""

            # ── Rb.41 — Dopunske jedinice ────────────────────────────
            supplementary_unit_code = _txt(item_el, "Supplementary_unit_code")
            supplementary_qty_str = _txt(item_el, "Supplementary_unit_quantity")
            try:
                supplementary_unit_qty = float(supplementary_qty_str) if supplementary_qty_str else 0.0
            except ValueError:
                supplementary_unit_qty = 0.0

            # ── Rb.42 — Vrijednost ───────────────────────────────────
            item_value_str = _txt(item_el, "Item_value")
            currency = _txt(item_el, "Currency")
            try:
                item_value = float(item_value_str) if item_value_str else 0.0
            except ValueError:
                item_value = 0.0
            if not currency:
                currency = "EUR"

            # ── Rb.44 — Priloženi dokumenti (tekstualna polja) ───────
            attached_doc_fields = [""] * 5
            doc_idx = 0
            for att_el in item_el.iter(
                f"{{{ns.get('n', '')}}}Attached_documents" if ns else "Attached_documents"
            ):
                code = _txt(att_el, "Attached_document_code")
                ref = _txt(att_el, "Attached_document_reference")
                if code and doc_idx < 5:
                    attached_doc_fields[doc_idx] = f"{code} ({ref})" if ref else code
                    doc_idx += 1

            # ── Rb.44 — Strukturirani prilozi ────────────────────────
            attached_documents = []
            for att_el in item_el.iter(
                f"{{{ns.get('n', '')}}}Attached_documents" if ns else "Attached_documents"
            ):
                code = _txt(att_el, "Attached_document_code")
                name = _txt(att_el, "Attached_document_name")
                ref = _txt(att_el, "Attached_document_reference")
                from_rule_str = _txt(att_el, "Attached_document_from_rule")
                from_rule = from_rule_str == "1" if from_rule_str else False
                if code:
                    attached_documents.append(
                        AttachedDocument(
                            code=code, name=name, number=ref, from_rule=from_rule
                        )
                    )

            # ── Rb.46 — Statistička vrijednost ───────────────────────
            stat_value_str = _txt(item_el, "Statistical_value")
            try:
                statistical_value = float(stat_value_str) if stat_value_str else 0.0
            except ValueError:
                statistical_value = 0.0

            # ── Kreiraj NaimenovanjeDraft ────────────────────────────
            draft = NaimenovanjeDraft(
                item_id=item_id,
                ordinal_no=ordinal,
                # Rb.31
                package_marks=package_marks,
                package_qty=float(package_qty) if package_qty else 0.0,
                package_code=package_code,
                package_name=package_name,
                goods_description=goods_description,
                goods_trade_name=trade_name,
                tariff_description1=tariff_desc1,
                tariff_description2=tariff_desc2,
                container_number1=container_number1,
                container_number2=container_number2,
                # Rb.33
                tariff_code=tariff_code,
                tariff_suffix=tariff_suffix,
                # Rb.34
                origin_country_code=origin_country_code,
                origin_country_name=origin_country_name,
                # Rb.36
                preference_code=preference_code,
                preference_name=preference_name,
                # Rb.35/38
                gross_mass_kg=gross_mass_kg,
                net_mass_kg=net_mass_kg,
                # Rb.37
                procedure_code=procedure_code,
                procedure_prev_code=procedure_prev_code,
                # Rb.39
                quota_code=quota_code,
                # Rb.40
                previous_document=previous_document,
                previous_document2=previous_document2,
                previous_document3=previous_document3,
                # Rb.41
                supplementary_unit_code=supplementary_unit_code,
                supplementary_unit_qty=supplementary_unit_qty,
                # Rb.42
                item_value=item_value,
                currency=currency,
                # Rb.44
                attached_document1=attached_doc_fields[0],
                attached_document2=attached_doc_fields[1],
                attached_document3=attached_doc_fields[2],
                attached_document4=attached_doc_fields[3],
                attached_document5=attached_doc_fields[4],
                attached_documents=attached_documents,
                # Rb.46
                statistical_value=statistical_value,
            )
            items.append(draft)

        self._log_operation(f"Parsirano {len(items)} naimenovanja iz XML-a")
        return items

    def _build_xml(self, data: Dict[str, Any], format_type: str = "world") -> ET.Element:
        """
        Gradi ASYCUDA XML strukturu.

        Args:
            data: Podaci zaglavlja
            format_type: Tip formata - "world" ili "pro" (default: "world")

        Returns:
            Root XML element
        """
        if format_type.lower() == "pro":
            return self._build_pro_xml(data)
        else:
            return self._build_world_xml(data)
    
    def _build_world_xml(self, data: Dict[str, Any]) -> ET.Element:
        """
        Gradi ASYCUDA World XML strukturu.
        
        Args:
            data: Podaci zaglavlja
        
        Returns:
            Root XML element
        """
        root = ET.Element("AsycudaDocument")
        
        # Identification
        ident = ET.SubElement(root, "Identification")
        type_elem = ET.SubElement(ident, "Type")
        
        if 'deklaracija_1' in data:
            ET.SubElement(type_elem, "Type_of_declaration").text = data['deklaracija_1']
        if 'deklaracija_2' in data:
            ET.SubElement(type_elem, "Type_of_Declaration_X").text = data['deklaracija_2']
        if 'deklaracija_3' in data:
            ET.SubElement(type_elem, "Declaration_gen_procedure_code").text = data['deklaracija_3']
        
        # Exporter
        if data.get('izvoznik_id'):
            exporter = ET.SubElement(root, "Exporter")
            ET.SubElement(exporter, "ID").text = data.get('izvoznik_id', '')
            ET.SubElement(exporter, "Name").text = data.get('izvoznik_r1', '')
            ET.SubElement(exporter, "Address").text = data.get('izvoznik_r2', '')
            ET.SubElement(exporter, "City").text = data.get('izvoznik_r3', '')
            ET.SubElement(exporter, "PostalCode").text = data.get('izvoznik_r4', '')
            ET.SubElement(exporter, "Country").text = data.get('izvoznik_r5', '')
        
        # Consignee
        if data.get('primalac_id'):
            consignee = ET.SubElement(root, "Consignee")
            ET.SubElement(consignee, "ID").text = data.get('primalac_id', '')
            ET.SubElement(consignee, "Name").text = data.get('primalac_r1', '')
            ET.SubElement(consignee, "Address").text = data.get('primalac_r2', '')
        
        # Declarant
        if data.get('deklarant_id'):
            declarant = ET.SubElement(root, "Declarant")
            ET.SubElement(declarant, "ID").text = data.get('deklarant_id', '')
            ET.SubElement(declarant, "Name").text = data.get('deklarant_r1', '')
        
        return root
    
    def _build_pro_xml(self, data: Dict[str, Any]) -> ET.Element:
        """
        Gradi ASYCUDA Pro XML strukturu.
        
        Args:
            data: Podaci zaglavlja
        
        Returns:
            Root XML element
        """
        # ASYCUDA Pro namespace
        ns = "http://www.asycuda.org/asycuda-pro"
        root = ET.Element(f"{{{ns}}}Declaration")
        root.set("xmlns", ns)
        
        # Osnovni podaci
        if 'broj_deklaracije' in data:
            decl_num = ET.SubElement(root, f"{{{ns}}}DeclarationNumber")
            decl_num.text = str(data['broj_deklaracije'])
        
        if 'datum' in data:
            decl_date = ET.SubElement(root, f"{{{ns}}}DeclarationDate")
            decl_date.text = str(data['datum'])
        
        if 'vrsta_deklaracije' in data:
            decl_type = ET.SubElement(root, f"{{{ns}}}DeclarationType")
            decl_type.text = str(data['vrsta_deklaracije'])
        
        # Izvoznik
        if data.get('izvoznik_id') or data.get('izvoznik_naziv'):
            exporter = ET.SubElement(root, f"{{{ns}}}Exporter")
            
            if 'izvoznik_id' in data:
                exp_id = ET.SubElement(exporter, f"{{{ns}}}ID")
                exp_id.text = str(data['izvoznik_id'])
            
            if 'izvoznik_naziv' in data:
                exp_name = ET.SubElement(exporter, f"{{{ns}}}Name")
                exp_name.text = str(data['izvoznik_naziv'])
        
        # Primalac
        if data.get('primalac_id') or data.get('primalac_naziv'):
            consignee = ET.SubElement(root, f"{{{ns}}}Consignee")
            
            if 'primalac_id' in data:
                cons_id = ET.SubElement(consignee, f"{{{ns}}}ID")
                cons_id.text = str(data['primalac_id'])
            
            if 'primalac_naziv' in data:
                cons_name = ET.SubElement(consignee, f"{{{ns}}}Name")
                cons_name.text = str(data['primalac_naziv'])
        
        # Transport
        if data.get('transport_id') or data.get('aktivno_transport'):
            transport = ET.SubElement(root, f"{{{ns}}}TransportMeans")
            
            if 'transport_id' in data:
                trans_id = ET.SubElement(transport, f"{{{ns}}}ID")
                trans_id.text = str(data['transport_id'])
            
            if 'aktivno_transport' in data:
                trans_nat = ET.SubElement(transport, f"{{{ns}}}Nationality")
                trans_nat.text = str(data['aktivno_transport'])

        return root

    # ============================================================
    # VALIDACIJA
    # ============================================================

    def validate(
        self,
        view_data: Dict[str, Any],
        draft: DeclarationDraft,
        import_attached_docs: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Kompleksna validacija zaglavlja prije XML exporta.

        Provjerava:
        1. Obavezna polja — da li su popunjena
        2. Sinhronizaciju — da li su podaci ažurni u odnosu na draft
           (npr. iznos iz fakture, valuta, težine)
        3. Konzistentnost — da li su povezana polja logična
        4. Priložene dokumente — export blokiran ako se ništa nije promijenilo od importa

        Args:
            view_data: Dictionary iz view.get_data()
            draft: Trenutni DeclarationDraft
            import_attached_docs: Snapshot dokumenata iz XML import-a
                                  (None = nije bilo import-a)

        Returns:
            {
                'valid': bool,
                'errors': List[Dict],   # Kritične greške (blokiraju export)
                'warnings': List[Dict], # Upozorenja (ne blokiraju export)
            }
        """
        errors: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []

        # ── 1. Obavezna polja ─────────────────────────────────────────────
        required_fields = {
            # Rubrika — key u view_data          — labela za poruku
            "deklaracija_1": ("1/1", "Šifra deklaracije"),
            "deklaracija_oznaka": ("1/1", "Oznaka postupka"),
            # deklaracija_a (polje 1/2) nema UI widget — auto-popunjava se,
            # nije obavezna za validaciju jer korisnik ne može ručno da je unese
            # izvoznik_r2 (adresa) nije obavezna — može biti prazna
            "izvoznik_r1": ("2", "Naziv izvoznika"),
            "izvoznik_r3": ("2", "Grad izvoznika"),
            "izvoznik_r5": ("2", "Država izvoznika"),
            "primalac_r1": ("8", "Naziv primaoca"),
            "primalac_r2": ("8", "Adresa primaoca"),
            "primalac_r3": ("8", "Grad primaoca"),
            # primalac_r5 (država primaoca) nije obavezna
            "deklarant_r1": ("14", "Naziv deklaranta"),
            "deklarant_r2": ("14", "Adresa deklaranta"),
            "deklarant_r3": ("14", "Grad deklaranta"),
            "transport_id": ("18", "Registracija trans. sredstva"),
            "aktivno_transport": ("21", "Registracija na granici"),
            "vid_25": ("25", "Vid unutra"),
            "uslovi_kod": ("20", "Uslovi isporuke — kod"),
            "uslovi_mjesto": ("20", "Uslovi isporuke — mjesto"),
            "valuta": ("22", "Valuta"),
            "iznos": ("22", "Iznos fakture"),
        }

        for key, (rule, label) in required_fields.items():
            value = view_data.get(key, "")
            # Poseban tretman za checkbox i numeričke vrijednosti
            if key == "iznos":
                if not value or float(str(value).replace(",", ".").strip() or "0") == 0:
                    errors.append({
                        "rule": rule,
                        "field": label,
                        "message": f"Rb.{rule} — {label}: polje je prazno ili nula",
                    })
                continue
            if not value or str(value).strip() == "":
                errors.append({
                    "rule": rule,
                    "field": label,
                    "message": f"Rb.{rule} — {label}: polje je prazno",
                })

        # ── 2. Sinhronizacija sa draft-om (detekcija zastarjelih podataka) ─
        invoice_lines = getattr(draft, "invoice_lines", None) or []

        # 2a. Iznos fakture — mora odgovarati sumi invoice_lines
        iznos_iz_fakture = sum(
            getattr(l, "iznos", 0.0) or 0.0 for l in invoice_lines
        )
        view_iznos_str = str(view_data.get("iznos", "0")).replace(",", ".").strip()
        try:
            view_iznos = float(view_iznos_str) if view_iznos_str else 0.0
        except ValueError:
            view_iznos = 0.0

        if invoice_lines and iznos_iz_fakture > 0:
            if abs(view_iznos - iznos_iz_fakture) > 0.01:
                errors.append({
                    "rule": "22",
                    "field": "Iznos fakture",
                    "message": (
                        f"Rb.22 — Iznos fakture NIJE ažuriran: "
                        f"forma ima {view_iznos:.2f}, faktura ima {iznos_iz_fakture:.2f}. "
                        f"Uvezite ponovo XML ili ručno ispravite iznos."
                    ),
                    "fixable": True,
                    "fix_action": "auto_update_iznos",
                })

        # 2b. Valuta — mora odgovarati valuti iz invoice_lines
        view_valuta = str(view_data.get("valuta", "")).strip()
        draft_valuta = ""
        for line in invoice_lines:
            v = getattr(line, "valuta", "") or ""
            if v:
                draft_valuta = v
                break

        if invoice_lines and draft_valuta and view_valuta != draft_valuta:
            warnings.append({
                "rule": "22",
                "field": "Valuta",
                "message": (
                    f"Rb.22 — Valuta se razlikuje: forma ima '{view_valuta}', "
                    f"faktura ima '{draft_valuta}'."
                ),
                "fixable": True,
                "fix_action": "auto_update_valuta",
            })

        # 2c. Težine — ukupna bruto/neto iz naimenovanja vs zaglavlje
        items = getattr(draft, "items", None) or []
        if items:
            total_bruto = sum(getattr(it, "gross_mass_kg", 0.0) or 0.0 for it in items)
            total_neto = sum(getattr(it, "net_mass_kg", 0.0) or 0.0 for it in items)
            # Ako postoje stavke, a nema težina — warning
            if total_bruto == 0 and total_neto == 0:
                warnings.append({
                    "rule": "35/38",
                    "field": "Masa",
                    "message": (
                        "Rb.35/38 — Ukupna masa je 0. Provjerite da li su "
                        "naimenovanja popunjena sa bruto/neto masama."
                    ),
                })

        # 2d. Broj stavki — mora odgovarati
        n_items_draft = len(draft.items) if draft.items else 0
        view_stavke = str(view_data.get("stavke", "")).strip()
        if view_stavke and view_stavke != str(n_items_draft):
            warnings.append({
                "rule": "5",
                "field": "Broj stavki",
                "message": (
                    f"Rb.5 — Broj stavki se razlikuje: forma ima {view_stavke}, "
                    f"naimenovanja imaju {n_items_draft}."
                ),
                "fixable": True,
                "fix_action": "auto_update_stavke",
            })

        # ── 3. Konzistentnost povezanih polja ──────────────────────────────

        # 3a. EX/IM konzistentnost — deklaracija_1 i deklaracija_oznaka
        dek_sifra = str(view_data.get("deklaracija_1", "")).strip()
        dek_oznaka = str(view_data.get("deklaracija_oznaka", "")).strip()
        if dek_sifra and dek_oznaka:
            valid_combos = {
                "IM": {"H", "I", "J", "K"},
                "EX": {"A", "C", "E"},
            }
            allowed = valid_combos.get(dek_sifra, set())
            if allowed and dek_oznaka not in allowed:
                errors.append({
                    "rule": "1",
                    "field": "Deklaracija",
                    "message": (
                        f"Rb.1 — Neispravna kombinacija: šifra='{dek_sifra}', "
                        f"oznaka='{dek_oznaka}'. Dozvoljene oznake za {dek_sifra}: "
                        f"{', '.join(sorted(allowed))}."
                    ),
                })

        # 3b. Kontejner — ako je čekiran, mora imati broj
        kontejner = view_data.get("kontejner", False)
        kontejner_broj = str(view_data.get("kontejner_broj", "")).strip()
        if kontejner and not kontejner_broj:
            warnings.append({
                "rule": "19",
                "field": "Kontejner",
                "message": "Rb.19 — Kontejner je označen, ali nedostaje broj kontejnera.",
            })

        # 3c. Priložene isprave — export blokiran ako obavezni dokumenti nisu ažurirani
        #
        # Obavezne šifre koje se mijenjaju za svaki uvoz:
        # VOZ=Vozarina, OST=Posebna dokumenta, PZT=Potvrda o zdravstvenom...,
        # N380=Faktura, DIS=Dispozicija, DV1=Prijava o carinskoj vrijednosti
        OBAVEZNE_SIFRE = {"VOZ", "OST", "PZT", "N380", "DIS", "DV1"}

        view_attached = view_data.get("attached_documents", [])

        if import_attached_docs is None:
            # Nije bilo XML import-a — nema provjere (novi dokument, korisnik upisuje ručno)
            pass
        elif import_attached_docs:
            # Napravi mape: šifra → referenca, samo za obavezne šifre
            def _docs_to_map(docs):
                result = {}
                for doc in docs if isinstance(docs, list) else []:
                    if isinstance(doc, dict):
                        code = (doc.get("code") or "").strip()
                        if code in OBAVEZNE_SIFRE:
                            result[code] = (doc.get("number") or "").strip()
                return result

            import_map = _docs_to_map(import_attached_docs)
            view_map = _docs_to_map(view_attached)

            self.logger.debug(f"Docs check — import: {import_map}, view: {view_map}")

            # Provjeri koje obavezne šifre imaju nepromijenjenu referencu
            neazurirani = []
            for sifra, import_ref in import_map.items():
                view_ref = view_map.get(sifra, "")
                if import_ref and view_ref == import_ref:
                    neazurirani.append(f"{sifra} ({import_ref})")

            if neazurirani:
                errors.append({
                    "rule": "attached_docs",
                    "field": "Priloženi dokumenti",
                    "message": (
                        "Priloženi dokumenti — Sljedeće reference nisu ažurirane od zadnjeg uvoza: "
                        f"{', '.join(neazurirani)}. "
                        "Unesite ispravne reference za ovaj uvoz, pa ponovite export."
                    ),
                })
                self.logger.warning(f"Export blocked: neažurirani dokumenti: {neazurirani}")
                self.logger.warning("Export blocked: attached docs unchanged from import")

        # ── Rezultat ───────────────────────────────────────────────────────
        valid = len(errors) == 0

        return {
            "valid": valid,
            "errors": errors,
            "warnings": warnings,
            "error_count": len(errors),
            "warning_count": len(warnings),
        }
