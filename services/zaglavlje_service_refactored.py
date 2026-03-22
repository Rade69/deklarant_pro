# services/zaglavlje_service_refactored.py

"""
Refaktorisani ZaglavljeService koji koristi BaseTabService.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from database.db import get_db_connection
from services.base_service import BaseTabService
from utils.exceptions import ValidationError, DatabaseError
from core.draft.draft import DeclarationDraft
from utils.cache import cache_database_query, get_database_cache


class ZaglavljeService(BaseTabService):
    """
    Refaktorisani ZaglavljeService koji nasljeđuje BaseTabService.
    
    Odgovornosti:
    - Validacija podataka zaglavlja
    - Čuvanje/učitavanje iz baze
    - Transformacija podataka između draft-a i UI podataka
    """
    
    def __init__(self):
        """Inicijalizacija ZaglavljeService sa BaseTabService."""
        super().__init__()
        self.logger = logging.getLogger(__name__)
    
    def validate(self, data: Dict[str, Any]) -> bool:
        """
        Validacija podataka zaglavlja.
        
        Args:
            data: Dictionary sa podacima zaglavlja
            
        Returns:
            True ako su podaci validni
            
        Raises:
            ValidationError: Ako podaci nisu validni
        """
        # Validacija obaveznih polja
        required_fields = [
            'broj_deklaracije',
            'datum',
            'vrsta_deklaracije',
            'izvoznik_id',
            'primalac_id'
        ]
        
        for field in required_fields:
            if not data.get(field):
                raise ValidationError(
                    f"Obavezno polje '{field}' je prazno",
                    field=field
                )
        
        # Validacija formata broja deklaracije
        broj_deklaracije = data.get('broj_deklaracije', '')
        if not broj_deklaracije or not broj_deklaracije.strip():
            raise ValidationError(
                "Broj deklaracije je obavezno polje",
                field="broj_deklaracije"
            )
        
        # Validacija datuma
        datum = data.get('datum')
        if datum:
            try:
                # Pokušaj parsiranja datuma
                if isinstance(datum, str):
                    # Ako je string, pokušaj parsirati
                    from datetime import datetime
                    datetime.strptime(datum, '%Y-%m-%d')
            except ValueError:
                raise ValidationError(
                    f"Nevalidan format datuma: {datum}",
                    field="datum"
                )
        
        return True
    
    def load_from_draft(self, draft: DeclarationDraft) -> Dict[str, Any]:
        """
        Konvertuje DeclarationDraft u dictionary za UI prikaz.
        
        Args:
            draft: DeclarationDraft objekat
            
        Returns:
            Dictionary sa podacima za prikaz u UI
        """
        if not draft:
            return {}
        
        return {
            'broj_deklaracije': draft.broj_deklaracije,
            'datum': draft.datum,
            'vrsta_deklaracije': draft.vrsta_deklaracije,
            'tip_postupka': draft.tip_postupka,
            'izvoznik_id': draft.izvoznik_id,
            'primalac_id': draft.primalac_id,
            'deklarant_id': draft.deklarant_id,
            'carinarnica': draft.carinarnica,
            'valuta': draft.valuta,
            'ukupna_tezina': draft.ukupna_tezina,
            'ukupna_vrijednost': draft.ukupna_vrijednost,
            'broj_stavki': draft.broj_stavki,
            'status': draft.status
        }
    
    def save_to_draft(self, draft: DeclarationDraft, data: Dict[str, Any]) -> DeclarationDraft:
        """
        Konvertuje UI podatke u DeclarationDraft.
        
        Args:
            draft: Postojeći draft (može biti prazan)
            data: Podaci iz UI forme
            
        Returns:
            Ažurirani DeclarationDraft
        """
        if draft is None:
            draft = DeclarationDraft()
        
        # Mapiranje podataka iz UI u draft
        draft.broj_deklaracije = data.get('broj_deklaracije', '')
        draft.datum = data.get('datum')
        draft.vrsta_deklaracije = data.get('vrsta_deklaracije')
        draft.tip_postupka = data.get('tip_postupka')
        draft.izvoznik_id = data.get('izvoznik_id')
        draft.primalac_id = data.get('primalac_id')
        draft.deklarant_id = data.get('deklarant_id')
        draft.carinarnica = data.get('carinarnica')
        draft.valuta = data.get('valuta')
        draft.ukupna_tezina = data.get('ukupna_tezina', 0.0)
        draft.ukupna_vrijednost = data.get('ukupna_vrijednost', 0.0)
        draft.broj_stavki = data.get('broj_stavki', 0)
        draft.status = data.get('status', 'DRAFT')
        
        return draft
    
    def save_to_database(self, data: Dict[str, Any]) -> bool:
        """
        Sačuvaj zaglavlje u bazu podataka.
        
        Args:
            data: Podaci zaglavlja
            
        Returns:
            True ako je uspješno sačuvano
            
        Raises:
            ValidationError: Ako podaci nisu validni
            DatabaseError: Ako dođe do greške prilikom čuvanja
        """
        # Validacija podataka
        self.validate(data)
        
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Provjeri da li zapis već postoji
                    cur.execute(
                        "SELECT 1 FROM zaglavlja WHERE broj_deklaracije = %s",
                        (data['broj_deklaracije'],)
                    )
                    
                    if cur.fetchone():
                        # Update postojećeg zapisa
                        cur.execute("""
                            UPDATE zaglavlja SET
                                datum = %s,
                                vrsta_deklaracije = %s,
                                tip_postupka = %s,
                                izvoznik_id = %s,
                                primalac_id = %s,
                                deklarant_id = %s,
                                carinarnica = %s,
                                valuta = %s,
                                ukupna_tezina = %s,
                                ukupna_vrijednost = %s,
                                broj_stavki = %s,
                                status = %s,
                                updated_at = NOW()
                            WHERE broj_deklaracije = %s
                        """, (
                            data.get('datum'),
                            data.get('vrsta_deklaracije'),
                            data.get('tip_postupka'),
                            data.get('izvoznik_id'),
                            data.get('primalac_id'),
                            data.get('deklarant_id'),
                            data.get('carinarnica'),
                            data.get('valuta'),
                            data.get('ukupna_tezina', 0),
                            data.get('ukupna_vrijednost', 0),
                            data.get('broj_stavki', 0),
                            data.get('status', 'DRAFT'),
                            data['broj_deklaracije']
                        ))
                    else:
                        # Insert novog zapisa
                        cur.execute("""
                            INSERT INTO zaglavlja (
                                broj_deklaracije, datum, vrsta_deklaracije,
                                tip_postupka, izvoznik_id, primalac_id,
                                deklarant_id, carinarnica, valuta,
                                ukupna_tezina, ukupna_vrijednost, broj_stavki,
                                status, created_at, updated_at
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()
                            )
                        """, (
                            data['broj_deklaracije'],
                            data.get('datum'),
                            data.get('vrsta_deklaracije'),
                            data.get('tip_postupka'),
                            data.get('izvoznik_id'),
                            data.get('primalac_id'),
                            data.get('deklarant_id'),
                            data.get('carinarnica'),
                            data.get('valuta'),
                            data.get('ukupna_tezina', 0),
                            data.get('ukupna_vrijednost', 0),
                            data.get('broj_stavki', 0),
                            data.get('status', 'DRAFT')
                        ))
                    
                    conn.commit()
                    self._log_operation("save_zaglavlje", success=True)
                    return True
                    
        except Exception as e:
            self._log_operation("save_zaglavlje", success=False, details=str(e))
            raise DatabaseError(f"Greška pri čuvanju zaglavlja: {str(e)}")
    
    @cache_database_query(ttl=300)  # Cache za 5 minuta
    def load_from_database(self, broj_deklaracije: str) -> Dict[str, Any]:
        """
        Učitaj zaglavlje iz baze.
        
        Args:
            broj_deklaracije: Broj deklaracije
            
        Returns:
            Dictionary sa podacima zaglavlja ili prazan dict ako nije pronađeno
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT * FROM zaglavlja 
                        WHERE broj_deklaracije = %s
                    """, (broj_deklaracije,))
                    
                    row = cur.fetchone()
                    if row:
                        return dict(row)
                    return {}
                        
        except Exception as e:
            self._log_operation("load_zaglavlje", success=False, details=str(e))
            raise DatabaseError(f"Greška pri učitavanju zaglavlja: {str(e)}")
    
    def delete_from_database(self, broj_deklaracije: str) -> bool:
        """
        Obriši zaglavlje iz baze.
        
        Args:
            broj_deklaracije: Broj deklaracije za brisanje
            
        Returns:
            True ako je uspješno obrisano
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM zaglavlja WHERE broj_deklaracije = %s",
                        (broj_deklaracije,)
                    )
                    conn.commit()
                    
                    if cur.rowcount > 0:
                        self._log_operation("delete_zaglavlje", success=True)
                        return True
                    else:
                        return False
                        
        except Exception as e:
            self._log_operation("delete_zaglavlje", success=False, details=str(e))
            raise DatabaseError(f"Greška pri brisanju zaglavlja: {str(e)}")
    
    @cache_database_query(ttl=60)  # Cache za 1 minutu (kraći TTL zbog čestih promjena)
    def search_zaglavlja(self, search_term: str = None, 
                        status: str = None, 
                        start_date: str = None,
                        end_date: str = None,
                        limit: int = 100,
                        offset: int = 0) -> List[Dict[str, Any]]:
        """
        Pretraži zaglavlja po različitim kriterijumima.
        
        Args:
            search_term: Tekst za pretragu (broj deklaracije, izvoznik, primalac)
            status: Status filter
            start_date: Početni datum
            end_date: Krajnji datum
            limit: Maksimalan broj rezultata
            offset: Offset za paginaciju
            
        Returns:
            Lista zaglavlja koja zadovoljavaju kriterijume
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    query = """
                        SELECT * FROM zaglavlja 
                        WHERE 1=1
                    """
                    params = []
                    
                    # Build WHERE clause
                    where_clauses = []
                    
                    if search_term:
                        where_clauses.append("""
                            (broj_deklaracije ILIKE %s OR 
                             izvoznik_id::text ILIKE %s OR
                             primalac_id::text ILIKE %s)
                        """)
                        search_pattern = f"%{search_term}%"
                        params.extend([search_pattern, search_pattern, search_pattern])
                    
                    if status:
                        where_clauses.append("status = %s")
                        params.append(status)
                    
                    if start_date:
                        where_clauses.append("datum >= %s")
                        params.append(start_date)
                    
                    if end_date:
                        where_clauses.append("datum <= %s")
                        params.append(end_date)
                    
                    if where_clauses:
                        query += " AND " + " AND ".join(where_clauses)
                    
                    query += " ORDER BY datum DESC, broj_deklaracije DESC"
                    query += " LIMIT %s OFFSET %s"
                    params.extend([limit, offset])
                    
                    cur.execute(query, params)
                    return [dict(row) for row in cur.fetchall()]
                    
        except Exception as e:
            self._log_operation("search_zaglavlja", success=False, details=str(e))
            raise DatabaseError(f"Greška pri pretrazi zaglavlja: {str(e)}")
    
    @cache_database_query(ttl=300)  # Cache za 5 minuta
    def get_statistika(self) -> Dict[str, Any]:
        """
        Vrati statističke podatke o zaglavljima.
        
        Returns:
            Dictionary sa statističkim podacima
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Ukupan broj zaglavlja
                    cur.execute("SELECT COUNT(*) as total FROM zaglavlja")
                    total = cur.fetchone()['count']
                    
                    # Broj po statusu
                    cur.execute("""
                        SELECT status, COUNT(*) as count 
                        FROM zaglavlja 
                        GROUP BY status
                    """)
                    status_counts = dict(cur.fetchall())
                    
                    # Broj po mjesecima (zadnjih 6 mjeseci)
                    cur.execute("""
                        SELECT 
                            TO_CHAR(datum, 'YYYY-MM') as month,
                            COUNT(*) as count
                        FROM zaglavlja 
                        WHERE datum >= CURRENT_DATE - INTERVAL '6 months'
                        GROUP BY TO_CHAR(datum, 'YYYY-MM')
                        ORDER BY month
                    """)
                    monthly_counts = dict(cur.fetchall())
                    
                    return {
                        'total': total,
                        'by_status': status_counts,
                        'monthly_counts': monthly_counts
                    }
                    
        except Exception as e:
            self._log_operation("get_statistika", success=False, details=str(e))
            raise DatabaseError(f"Greška pri dobavljanju statistike: {str(e)}")
    
    def export_to_csv(self, filepath: str, start_date: str = None, end_date: str = None) -> str:
        """
        Izvezi zaglavlja u CSV fajl.
        
        Args:
            filepath: Putanja do CSV fajla
            start_date: Početni datum filtera
            end_date: Krajnji datum filtera
            
        Returns:
            Putanja do kreiranog CSV fajla
        """
        try:
            zaglavlja = self.search_zaglavlja(
                start_date=start_date,
                end_date=end_date,
                limit=10000  # Ograničenje za export
            )
            
            if not zaglavlja:
                raise ValidationError("Nema podataka za izvoz")
            
            import csv
            import os
            
            # Kreiraj direktorijum ako ne postoji
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                if zaglavlja:
                    # Koristi ključeve prvog zapisa kao header
                    fieldnames = zaglavlja[0].keys()
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    
                    writer.writeheader()
                    for row in zaglavlja:
                        writer.writerow(row)
            
            self._log_operation("export_csv", success=True, 
                              details=f"Exported {len(zaglavlja)} records to {filepath}")
            return filepath
            
        except Exception as e:
            self._log_operation("export_csv", success=False, details=str(e))
            raise Exception(f"Greška pri izvozu u CSV: {str(e)}")
    
    @cache_database_query(ttl=300)  # Cache za 5 minuta
    def validate_duplicate(self, broj_deklaracije: str) -> bool:
        """
        Provjeri da li zaglavlje sa datim brojem deklaracije već postoji.
        
        Args:
            broj_deklaracije: Broj deklaracije za provjeru
            
        Returns:
            True ako već postoji, False ako ne postoji
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT 1 FROM zaglavlja 
                        WHERE broj_deklaracije = %s
                    """, (broj_deklaracije,))
                    
                    return cur.fetchone() is not None
                    
        except Exception as e:
            self._log_operation("validate_duplicate", success=False, details=str(e))
            raise DatabaseError(f"Greška pri provjeri duplikata: {str(e)}")
    
    def get_validation_errors(self, data: Dict[str, Any]) -> List[str]:
        """
        Vrati listu grešaka u validaciji.
        
        Args:
            data: Podaci za validaciju
            
        Returns:
            Lista grešaka (prazna lista ako nema grešaka)
        """
        errors = []
        
        # Provjera obaveznih polja
        required_fields = [
            'broj_deklaracije',
            'datum',
            'vrsta_deklaracije',
            'izvoznik_id',
            'primalac_id'
        ]
        
        for field in required_fields:
            if not data.get(field):
                errors.append(f"Polje '{field}' je obavezno")
        
        # Validacija formata broja deklaracije
        broj_deklaracije = data.get('broj_deklaracije', '')
        if broj_deklaracije and not broj_deklaracije.strip():
            errors.append("Broj deklaracije ne može biti prazan")
        
        # Validacija datuma
        datum = data.get('datum')
        if datum:
            try:
                from datetime import datetime
                datetime.strptime(datum, '%Y-%m-%d')
            except ValueError:
                errors.append("Datum mora biti u formatu YYYY-MM-DD")
        
        return errors