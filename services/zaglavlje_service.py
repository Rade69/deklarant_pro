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
from core.draft.draft import DeclarationDraft


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
    
    def load_from_xml(self, filepath: str) -> Dict[str, Any]:
        """
        Učitaj zaglavlje iz XML fajla.
        
        Args:
            filepath: Putanja do XML fajla
        
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
            return self._parse_xml(root)
            
        except ET.ParseError as e:
            raise ValueError(f"Neispravan XML format: {e}")
    
    def export_to_xml(self, data: Dict[str, Any], filepath: str) -> bool:
        """
        Eksportuj zaglavlje u XML fajl.
        
        Args:
            data: Podaci zaglavlja
            filepath: Putanja do XML fajla
        
        Returns:
            True ako je uspješno
        """
        try:
            root = self._build_xml(data)
            tree = ET.ElementTree(root)
            tree.write(filepath, encoding='utf-8', xml_declaration=True)
            
            self.logger.info(f"XML eksportovan: {filepath}")
            return True
            
        except Exception as e:
            self.logger.error(f"Greška pri XML eksportu: {e}")
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

        # Rubrika 21 - Aktivno transportno sredstvo
        data['aktivno_transport'] = getattr(draft, 'aktivno_transport', '') or ''

        # Rubrika 25, 26, 27 - Vid unutra/granica (draft nema vid_27 polje)
        data['vid_25'] = getattr(draft, 'vid_unutra', '') or ''
        data['vid_26'] = getattr(draft, 'vid_granica', '') or ''
        data['vid_27'] = ''  # nije u draft modelu

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
        data['valuta'] = getattr(draft, 'valuta', '') or ''
        iznos_val = getattr(draft, 'iznos', 0.0) or 0.0
        data['iznos'] = str(iznos_val) if iznos_val else ''
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
                    'from_rule': getattr(doc, 'from_rule', False),
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

        # Rubrika 21 - Aktivno transportno sredstvo
        draft.aktivno_transport = safe_get('aktivno_transport')

        # Rubrika 25, 26 - Vid unutra/granica (vid_27 nema u draft modelu)
        draft.vid_unutra = safe_get('vid_25')
        draft.vid_granica = safe_get('vid_26')

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
            # TODO: Implement when AttachedDocument model is available
            pass

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

        # ── Rb. 3, 4, 5: Obrasci, tovarni listovi, stavke ────────────────────
        prop = _find(root, "Property")
        if prop is not None:
            forms = _find(prop, "Forms")
            if forms is not None:
                data['obrazac_1'] = _txt(forms, "Number_of_the_form")
                data['obrazac_2'] = _txt(forms, "Total_number_of_forms")
            nbers = _find(prop, "Nbers")
            if nbers is not None:
                data['tovarni_listovi'] = _txt(nbers, "Number_of_loading_lists")
                data['stavke'] = _txt(nbers, "Total_number_of_items")

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

        # ── Rb. 18, 19, 20, 21, 25, 26, 29, 30 ───────────────────────────────
        transport_el = _find(root, "Transport")
        if transport_el is not None:
            means = _find(transport_el, "Means_of_transport")
            if means is not None:
                border_info = _find(means, "Border_information")
                if border_info is not None:
                    data['transport_id'] = _txt(border_info, "Identity")
                    data['aktivno_transport'] = _txt(border_info, "Nationality")
                    data['vid_26'] = _txt(border_info, "Mode")
                data['vid_25'] = _txt(means, "Inland_mode_of_transport")

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
            def_pay = _find(financial, "Deffered_payment_reference")
            if def_pay is not None and def_pay.text:
                data['odgodjeno_placanje'] = def_pay.text.strip()

        # ── Rb. 49: Identifikacija skladišta ──────────────────────────────────
        warehouse = _find(root, "Warehouse")
        if warehouse is not None:
            wh_id = _find(warehouse, "Identification")
            if wh_id is not None and wh_id.text:
                data['identifikacija_skladista'] = wh_id.text.strip()

        # ── Troškovi: trosak_1..5 ─────────────────────────────────────────────
        valuation = _find(root, "Valuation")
        if valuation is not None:
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

        return data
    
    def _build_xml(self, data: Dict[str, Any]) -> ET.Element:
        """
        Gradi ASYCUDA XML strukturu.
        
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
