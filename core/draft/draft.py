from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Tuple
import uuid as _uuid


def _s(v: Any) -> str:
    return "" if v is None else str(v).strip()


def _f(v: Any) -> float:
    try:
        if v is None or v == "":
            return 0.0
        return float(str(v).replace(",", "."))
    except Exception:
        return 0.0


# =========================
# Parties (Exporter/Importer)
# =========================


@dataclass(slots=True)
class Party:
    name: str = ""
    address: str = ""
    city: str = ""
    country: str = ""
    vat_or_id: str = ""

    @classmethod
    def from_any(cls, v: Any) -> "Party":
        if isinstance(v, cls):
            return v
        if isinstance(v, dict):
            return cls(
                name=_s(v.get("name") or v.get("naziv") or v.get("Naziv")),
                address=_s(v.get("address") or v.get("adresa") or v.get("Adresa")),
                city=_s(v.get("city") or v.get("grad") or v.get("Grad")),
                country=_s(v.get("country") or v.get("drzava") or v.get("Drzava")),
                vat_or_id=_s(
                    v.get("vat_or_id") or v.get("id") or v.get("ID") or v.get("JIB")
                ),
            )
        return cls(name=_s(v))


# =========================
# Raw invoice line (imported)
# =========================


@dataclass(slots=True)
class InvoiceLine:
    """Sirova stavka iz fakture (XLSX/PDF) – normalizovana."""

    line_no: int = 0

    naziv_robe: str = ""
    tarifni_broj: str = ""
    zemlja_porijekla: str = ""
    povlastica: str = ""  # prazno = nije navedeno / nema

    jm: str = ""
    kolicina: float = 0.0
    cijena_jed: float = 0.0
    iznos: float = 0.0
    valuta: str = "EUR"

    bruto_kg: float = 0.0
    neto_kg: float = 0.0

    exporter: Party = field(default_factory=Party)
    importer: Party = field(default_factory=Party)

    raw: Dict[str, Any] = field(default_factory=dict)

    def key(self) -> Tuple[str, str, str]:
        """KLJUČ za grupisanje: tarifni broj + zemlja porijekla + povlastica."""
        return (_s(self.tarifni_broj), _s(self.zemlja_porijekla), _s(self.povlastica))

    @classmethod
    def from_any(cls, v: Any, default_currency: str = "EUR") -> "InvoiceLine":
        """Prihvata dict-ove iz različitih importera i normalizuje ih u InvoiceLine."""
        if isinstance(v, cls):
            return v
        if not isinstance(v, dict):
            return cls(naziv_robe=_s(v), valuta=default_currency)

        naziv = (
            v.get("naziv_robe")
            or v.get("Naziv robe")
            or v.get("opis")
            or v.get("description")
            or ""
        )
        tarif = (
            v.get("tarifni_broj")
            or v.get("Tarifni broj")
            or v.get("tarif")
            or v.get("hs")
            or ""
        )
        zemlja = (
            v.get("zemlja_porijekla")
            or v.get("Zemlja porijekla")
            or v.get("origin")
            or v.get("Country_of_origin_code")
            or ""
        )
        pref = (
            v.get("povlastica")
            or v.get("Povlastica")
            or v.get("preference")
            or v.get("Preference_code")
            or ""
        )

        jm = v.get("jm") or v.get("JM") or v.get("unit") or ""
        kolicina = _f(v.get("kolicina") or v.get("Kolicina") or v.get("qty") or 0)
        cijena_jed = _f(v.get("cijena_jed") or v.get("Cijena") or v.get("price") or 0)
        iznos = _f(v.get("iznos") or v.get("Iznos") or v.get("amount") or 0)
        valuta = _s(
            v.get("valuta") or v.get("Valuta") or v.get("currency") or default_currency
        )

        bruto = _f(v.get("bruto_kg") or v.get("Bruto") or v.get("gross") or 0)
        neto = _f(v.get("neto_kg") or v.get("Neto") or v.get("net") or 0)

        return cls(
            line_no=int(_f(v.get("line_no") or v.get("Line") or 0)),
            naziv_robe=_s(naziv),
            tarifni_broj=_s(tarif),
            zemlja_porijekla=_s(zemlja),
            povlastica=_s(pref),
            jm=_s(jm),
            kolicina=kolicina,
            cijena_jed=cijena_jed,
            iznos=iznos,
            valuta=valuta or default_currency,
            bruto_kg=bruto,
            neto_kg=neto,
            exporter=Party.from_any(v.get("exporter") or {}),
            importer=Party.from_any(v.get("importer") or {}),
            raw=dict(v),
        )


# =========================
# Item-level model (Naimenovanje)
# =========================


@dataclass(slots=True)
class AttachedDocument:
    """Rub.44 – jedan prilog."""

    code: str
    number: str


@dataclass(slots=True)
class NaimenovanjeDraft:
    """Jedno naimenovanje (stavka/agregat) u Draft-u."""

    item_id: str
    ordinal_no: int  # Rub.32

    # Rub.31 – pakovanja + opis robe (JCI kompleksna struktura)
    package_marks: str = ""           # oznake i br.
    package_qty: float = 0.0          # broj (npr. 5)
    package_code: str = ""            # kod (npr. PK, CT)
    package_name: str = ""            # opis pakovanja
    container_number1: str = ""       # kontejner 1
    container_number2: str = ""       # kontejner 2
    goods_description: str = ""       # glavni opis robe (textarea)
    goods_trade_name: str = ""        # trgovački naziv
    tariff_description1: str = ""     # opis tarifnog broja 1
    tariff_description2: str = ""     # opis tarifnog broja 2
    tariff_description3: str = ""     # opis tarifnog broja 3

    # Rub.33 – tarifni broj
    tariff_code: str = ""
    tariff_suffix: str = ""

    # Rub.34 – porijeklo
    origin_country_code: str = ""
    origin_country_name: str = ""

    # Rub.36 – povlastica
    preference_code: str = ""
    preference_name: str = ""

    # Rub.35/38 – mase
    gross_mass_kg: float = 0.0
    net_mass_kg: float = 0.0

    # Rub.37 – procedura (opciono)
    procedure_code: str = ""
    procedure_prev_code: str = ""

    # Rub.39 – kvota (opciono)
    quota_code: str = ""

    # Rub.40 – prethodni dokument (ručno)
    previous_document: str = ""

    # Rub.41 – dopunske jedinice (opciono)
    supplementary_unit_code: str = ""
    supplementary_unit_qty: float = 0.0

    # Rub.42 – vrijednost
    item_value: float = 0.0
    currency: str = "EUR"

    # Rub.44 – prilozi
    attached_documents: List[AttachedDocument] = field(default_factory=list)

    # Rub.46 – statistička vrijednost
    statistical_value: float = 0.0

    # Interne napomene / audit
    source_invoice_refs: List[str] = field(default_factory=list)
    notes: str = ""

    @property
    def package_label(self) -> str:
        if self.package_code and self.package_name:
            return f"{self.package_code} — {self.package_name}"
        return self.package_code or ""

    @property
    def grouping_key(self) -> Tuple[str, str, str]:
        return (
            _s(self.tariff_code),
            _s(self.origin_country_code),
            _s(self.preference_code),
        )


# =========================
# Declaration Draft (single source of truth)
# =========================


@dataclass
class DeclarationDraft:
    """
    Centralni radni objekat (jedini izvor istine).

    GUI:
      - učita draft -> napuni tabove
      - izmijeni tabove -> upiše nazad u draft

    Grouping:
      - invoice_lines -> items (naimenovanja)

    Export:
      - Draft -> XML
    """

    header: Dict[str, Any] = field(default_factory=dict)
    invoice_lines: List[InvoiceLine] = field(default_factory=list)
    items: List[NaimenovanjeDraft] = field(default_factory=list)
    prilozi: Dict[str, Any] = field(default_factory=dict)

    source_files: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    dirty: bool = False
    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )

    def mark_dirty(self) -> None:
        self.dirty = True

    def clear_dirty(self) -> None:
        self.dirty = False

    def ensure_min_items(self, n: int = 1) -> None:
        while len(self.items) < n:
            self.items.append(
                NaimenovanjeDraft(
                    item_id=str(_uuid.uuid4()),
                    ordinal_no=len(self.items) + 1,
                )
            )

    def add_item(self) -> NaimenovanjeDraft:
        """Dodaj novo naimenovanje i vrati ga."""
        new_item = NaimenovanjeDraft(
            item_id=str(_uuid.uuid4()),
            ordinal_no=len(self.items) + 1,
        )
        self.items.append(new_item)
        self.mark_dirty()
        return new_item

    def apply_to_all(self, field_name: str, value: Any) -> None:
        for it in self.items:
            setattr(it, field_name, value)
        self.mark_dirty()
