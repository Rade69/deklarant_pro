# importers/import_result.py

"""
Result objekat za PDF/Excel import sa dodatnim podacima.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from core.draft.draft import InvoiceLine, Party


@dataclass
class ImportResult:
    """
    Rezultat importa fakture sa dodatnim metadata podacima.

    Attributes:
        items: Lista InvoiceLine objekata
        bruto_kg: Ukupna bruto težina sa fakture (kg)
        neto_kg: Ukupna neto težina sa fakture (kg)
        invoice_name: Ime/broj fakture
        currency: Valuta (EUR, USD, itd.)
        is_combined: Da li je ovo kombinovani import (Excel + PDF)
        import_type: Tip importa ('loren_pdf', 'loren_excel', 'loren_combined', 'invoice')
        has_origin_statement: Da li faktura sadrži izjavu o poreklu (PE2)
        origin_statements: Lista detektovanih izjava o poreklu (za fakture sa više izjava)
        exporter: Party objekat sa podacima o izvozniku/pošiljaocu
        importer: Party objekat sa podacima o uvozniku/primaocu
    """
    items: List[InvoiceLine] = field(default_factory=list)
    bruto_kg: float = 0.0
    neto_kg: float = 0.0
    invoice_name: str = ""
    currency: str = "EUR"
    is_combined: bool = False  # Flag za kombinovane importe (Excel + PDF)
    import_type: str = "invoice"  # Tip importa (loren_pdf, loren_excel, loren_combined, invoice)
    has_origin_statement: bool = False  # Da li faktura sadrži izjavu o poreklu
    is_authorized_exporter: bool = False  # True = izjava ovlaštenog izvoznika (PE3)
    origin_statements: Optional[List] = None  # Lista OriginStatementMatch objekata
    warnings: List[str] = field(default_factory=list)  # Upozorenja koja treba prikazati korisniku
    exporter: Optional[Party] = None  # Izvoznik/pošiljalac iz fakture
    importer: Optional[Party] = None  # Uvoznik/primalac iz fakture
    consumed_paths: List[str] = field(default_factory=list)  # Putanje fajlova koje je ovaj import interno koristio (ne obrađivati ponovo)

    def __post_init__(self):
        # Ako nije eksplicitno postavljeno, izračunaj iz origin_statements
        if not self.is_authorized_exporter and self.origin_statements:
            self.is_authorized_exporter = any(
                getattr(s, 'tip_izjave', '') == 'ovlaseni_izvoznik'
                for s in self.origin_statements
            )

    def __len__(self) -> int:
        """Return number of items (for len() support)."""
        return len(self.items)

    def __getitem__(self, index: int | slice) -> InvoiceLine | List[InvoiceLine]:
        """Return item at index or slice (for indexing/slicing support)."""
        return self.items[index]

    def validate(self, allow_empty: bool = False) -> tuple[bool, list[str], list[str]]:
        """
        Parser-level validacija — provjera da su podaci fizički ispravni.

        Ne radi poslovnu logiku (duplikati, šifrarnici) — samo provjerava
        da parser nije vratio neispravne ili nepotpune podatke.

        Args:
            allow_empty: Ako True, 0 stavki nije greška (koristi se za packing listu
                         koja čeka par). Negativne težine i dalje blokiraju.

        Returns:
            (ok, errors, warnings)
            ok=False → import se ne smije nastaviti
        """
        errors: list[str] = []
        warnings: list[str] = []

        _KNOWN_CURRENCIES = {"EUR", "USD", "BAM", "CHF", "GBP", "SEK", "NOK", "DKK", "HRK", "RSD"}

        # --- razina ImportResult ---
        if not self.items and not allow_empty:
            errors.append("Parser nije pronašao nijednu stavku (0 stavki)")

        if self.currency and self.currency.upper() not in _KNOWN_CURRENCIES:
            warnings.append(f"Nepoznata valuta: '{self.currency}'")

        if self.bruto_kg < 0:
            errors.append(f"Negativna bruto težina: {self.bruto_kg} kg")

        if self.neto_kg < 0:
            errors.append(f"Negativna neto težina: {self.neto_kg} kg")

        if self.bruto_kg > 0 and self.neto_kg > 0 and self.neto_kg > self.bruto_kg:
            errors.append(
                f"Neto ({self.neto_kg} kg) > Bruto ({self.bruto_kg} kg) — fizički nemoguće"
            )

        # --- razina stavke ---
        for i, item in enumerate(self.items, 1):
            naziv = (item.naziv_robe or "").strip()
            if not naziv:
                warnings.append(f"Stavka {i}: prazan naziv robe")

            if item.kolicina <= 0:
                warnings.append(f"Stavka {i} ({naziv[:30] or '?'}): količina = {item.kolicina}")

            if item.cijena_jed < 0:
                errors.append(f"Stavka {i} ({naziv[:30] or '?'}): negativna cijena {item.cijena_jed}")

            if item.iznos < 0:
                errors.append(f"Stavka {i} ({naziv[:30] or '?'}): negativan iznos {item.iznos}")

            if item.bruto_kg > 0 and item.neto_kg > 0 and item.neto_kg > item.bruto_kg:
                warnings.append(
                    f"Stavka {i} ({naziv[:30] or '?'}): neto > bruto ({item.neto_kg} > {item.bruto_kg})"
                )

        # Dodaj warnings u self.warnings (dedup)
        existing = set(self.warnings)
        for w in warnings:
            if w not in existing:
                self.warnings.append(w)
                existing.add(w)

        ok = len(errors) == 0
        return ok, errors, warnings
