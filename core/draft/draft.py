from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Tuple, Callable
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
    product_code: str = ""  # Kod proizvoda iz fakture (za matching)
    tarifni_broj: str = ""
    tariff_suffix: str = "000"   # Precision_1 (000 za većinu, 100 za lijekove)
    zemlja_porijekla: str = ""
    povlastica: str = ""  # prazno = nije navedeno / nema

    # EUR.1 podaci
    eur1_number: str = ""           # Broj EUR.1 obrasca
    has_origin_statement: bool = False  # Da li stavka ima izjavu o poreklu (PE2/EUR1 eligible)
    no_preference: bool = False         # Eksplicitno "bez pref. porekla" — nema povlastice

    # Confidence level za zemlju porijekla (HIGH/MEDIUM/LOW/CONFLICT)
    country_confidence: str = ""  # "HIGH", "MEDIUM", "LOW", "CONFLICT"
    country_source: str = ""      # "PDF", "BAZA", "MATCH", "CONFLICT", "NONE"
    country_conflict_details: str = ""  # Detalji konflikta ako postoji

    # Sličnost tarifnog broja iz baze znanja (0.0-1.0)
    tariff_similarity: float = 0.0  # 1.0=tačan match, <1.0=fuzzy match

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

    # Mapiranje na naimenovanje (popunjava se nakon kreiranja naimenovanja)
    assigned_naimenovanje_id: str = ""
    assigned_naimenovanje_ordinal: int = 0  # Redni broj naimenovanja (32)

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
        product_code = (
            v.get("product_code")
            or v.get("kod")
            or v.get("Kod")
            or v.get("sifra")
            or v.get("code")
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
            product_code=_s(product_code),
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
    name: str = ""           # Attached_document_name (puni naziv tipa isprave)
    number: str = ""         # Attached_document_reference (broj/referenca)
    from_rule: bool = False  # True → Attached_document_from_rule=1 + pojavljuje se u Attached_doc_item


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

    # Rub.40 – prethodni dokumenti (ručno)
    previous_document: str = ""           # le_rubrika40_1
    previous_document2: str = ""          # le_rubrika40_2
    previous_document3: str = ""          # le_rubrika40_3

    # Rub.41 – dopunske jedinice (opciono)
    supplementary_unit_code: str = ""
    supplementary_unit_qty: float = 0.0

    # Rub.42 – vrijednost
    item_value: float = 0.0
    currency: str = "EUR"

    # Rub.44 – priložene isprave (ručno - tekstualna polja)
    attached_document1: str = ""          # le_rubrika44_1
    attached_document2: str = ""          # le_rubrika44_2
    attached_document3: str = ""          # le_rubrika44_3
    attached_document4: str = ""          # le_rubrika44_4
    attached_document5: str = ""          # le_rubrika44_5

    # Rub.44 – prilozi (strukturirani)
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

    # Callback za obaveštavanje o promenama
    _data_change_callbacks: List[Callable] = field(default_factory=list)

    # Zaglavlje deklaracije (rubrike 1-49)
    # Rubrika 1 - Deklaracija
    deklaracija_tip: str = ""      # EX ili IM (polje 1/1 sifra)
    deklaracija_oznaka: str = ""   # H/I/J/K za IM, A/C/E za EX (polje 1/1 oznaka)
    deklaracija_a: str = ""        # A/Z/B – tip deklaracije (polje 1/2)
    ured_odredista: str = ""       # npr. "CI Bijeljina" – read-only iz baze

    # Rubrika 2 - Izvoznik
    izvoznik_id: str = ""
    izvoznik_naziv: str = ""
    izvoznik_adresa: str = ""
    izvoznik_grad: str = ""
    izvoznik_postanski_broj: str = ""
    izvoznik_drzava: str = ""

    # Rubrika 8 - Primalac
    primalac_id: str = ""
    primalac_naziv: str = ""
    primalac_adresa: str = ""
    primalac_grad: str = ""
    primalac_postanski_broj: str = ""
    primalac_drzava: str = ""

    # Rubrika 14 - Deklarant
    deklarant_id: str = ""
    deklarant_naziv: str = ""
    deklarant_adresa: str = ""
    deklarant_grad: str = ""
    deklarant_postanski_broj: str = ""
    deklarant_drzava: str = ""
    deklarant_predstavnik: str = ""  # Predstavnik deklaranta (npr. "Marko Marković, dipl. ecc.")

    # Rubrika 18 - Identitet transp. sredstva
    transport_id: str = ""

    # Rubrika 19 - Kontejner
    kontejner: bool = False

    # Rubrika 18 - Identitet + nacionalnost pri polasku
    transport_nacionalnost: str = ""   # šifra države: BA, RS, DE...
    # Rubrika 19 - Kontejner
    kontejner_broj: str = ""           # broj kontejnera (vidljivo samo ako kontejner=True)
    # Rubrika 21 - Aktivno transp. sredstvo na granici + nacionalnost
    aktivno_transport: str = ""
    aktivno_transport_nat: str = ""    # nacionalnost na granici

    # Rubrika 25, 26, 27 - Vid unutra/granica i mjesto otvarača
    vid_unutra: str = ""
    vid_granica: str = ""
    mjesto_otvaraca: str = ""

    # Rubrika 29 - Izlazna carinarnica
    izlazna_carinarnica: str = ""

    # Rubrika 30 - Lokacija robe
    lokacija_robe: str = ""

    # Rubrika 3 - Obrasci
    obrazac_1: str = ""
    obrazac_2: str = ""

    # Rubrika 4 - Tovarni listovi
    tovarni_listovi: str = ""

    # Rubrika 5 - Stavke
    stavke: str = ""

    # Rubrika 6 - Uk. paketa
    uk_paketa: str = ""

    # Rubrika 7 - Ref.br.
    ref_br: str = ""

    # Rubrika 9 - Odgovorna zemlja
    odg_zemlja_1: str = ""
    odg_zemlja_2: str = ""
    odg_zemlja_3: str = ""
    odg_zemlja_4: str = ""

    # Rubrika 10, 11, 12, 13 - Zemlje
    zem_10: str = ""
    zem_11: str = ""
    zem_12: str = ""
    zem_13: str = ""

    # Rubrika 15 - Država izvoza
    drzava_izvoza_naziv: str = ""
    drzava_izvoza_sifra: str = ""

    # Rubrika 16 - Država porijekla
    drzava_porijekla: str = ""

    # Rubrika 17 - Država odredišta
    drzava_odredista_naziv: str = ""
    drzava_odredista_sifra: str = ""

    # Rubrika 20 - Uslovi isporuke
    uslovi_kod: str = ""
    uslovi_mjesto: str = ""

    # Rubrika 22, 23, 24 - Valuta
    valuta: str = ""
    iznos: float = 0.0
    kurs: float = 1.0
    vrsta_trans_1: str = ""
    vrsta_trans_2: str = ""

    # Rubrika 40 - Zbirna deklaracija / prethodni dokument
    rb40_tip: str = ""          # X / Y / Z
    rb40_skracenica: str = ""   # Šifra dokumenta (N380, N730 ...)
    rb40_broj: str = ""         # N° – broj/referenca dokumenta

    # Rubrika 48, 49 - Odgođeno plaćanje
    odgodjeno_placanje: str = ""
    identifikacija_skladista: str = ""

    # Troškovi
    trosak_1: str = "0,00"
    trosak_2: str = "0,00"
    trosak_3: str = "0,00"
    trosak_4: str = "0,00"
    trosak_5: str = "0,00"

    # Ostala polja
    header: Dict[str, Any] = field(default_factory=dict)
    invoice_lines: List[InvoiceLine] = field(default_factory=list)
    items: List[NaimenovanjeDraft] = field(default_factory=list)
    prilozi: Dict[str, Any] = field(default_factory=dict)

    # Rub.44 zaglavlja – priložene isprave koje važe za sve stavke
    header_attached_documents: List[AttachedDocument] = field(default_factory=list)

    source_files: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    dirty: bool = False
    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )

    def register_data_change_callback(self, callback: Callable) -> None:
        """Registruj callback koji će biti pozvan kada se podaci promene."""
        if callback not in self._data_change_callbacks:
            self._data_change_callbacks.append(callback)

    def unregister_data_change_callback(self, callback: Callable) -> None:
        """Ukloni callback iz liste."""
        if callback in self._data_change_callbacks:
            self._data_change_callbacks.remove(callback)

    def _notify_data_change(self) -> None:
        """Obavesti sve registrovane callback-ove o promeni podataka."""
        for callback in self._data_change_callbacks:
            try:
                callback()
            except Exception as e:
                print(f"⚠️ Greška u data change callback-u: {e}")

    def mark_dirty(self) -> None:
        """Označi draft kao promijenjen i obavesti sve callback-ove."""
        self.dirty = True
        self._notify_data_change()

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
