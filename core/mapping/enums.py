"""Enumeracije i konstante za mapiranje."""

from enum import Enum


class VrstaDeklaracije(Enum):
    """Vrste carinskih deklaracija."""

    IM4 = "IM4"  # Uvoz u slobodan promet
    IM7 = "IM7"  # Privremeni uvoz
    EX1 = "EX1"  # Izvoz
    EX2 = "EX2"  # Reeksport


class Procedura(Enum):
    """Carinske procedure."""

    UVOZ_SLOBODAN_PROMET = "40 00"
    PRIVREMENI_UVOZ = "53 00"
    IZVOZ = "10 00"
    REEKSPORT = "31 00"


class JedinicaMere(Enum):
    """Jedinice mere."""

    KG = "KGM"  # Kilogram
    KOM = "PCE"  # Komad
    L = "LTR"   # Litar
    M = "MTR"   # Metar
    M2 = "MTK"  # Kvadratni metar
    M3 = "MTQ"  # Kubni metar


class VrstaPakovanja(Enum):
    """Vrste pakovanja."""

    KARTON = "CT"  # Carton
    PALETA = "PX"  # Pallet
    KONTEJNER = "CN"  # Container
    VREĆA = "BG"  # Bag
    SANDUK = "BX"  # Box
    ROLNA = "RO"  # Roll


class Valuta(Enum):
    """Valute."""

    EUR = "EUR"
    USD = "USD"
    BAM = "BAM"
    RSD = "RSD"


class TipDokumenta(Enum):
    """Tipovi dokumenata."""

    FAKTURA = "380"  # Commercial invoice
    CMR = "730"      # CMR waybill
    EUR1 = "861"     # EUR1 movement certificate
    CERTIFIKAT = "865"  # Certificate of origin
    PAKET_LIST = "271"  # Packing list


# Mape za konverziju
ZEMLJA_KODOVI = {
    "Bosna i Hercegovina": "BA",
    "Srbija": "RS",
    "Hrvatska": "HR",
    "Njemačka": "DE",
    "Italija": "IT",
    "Austrija": "AT",
    "Slovenija": "SI",
    "Turska": "TR",
    "Kina": "CN",
}

POVLASTICA_KODOVI = {
    "CEFTA": "CEFTA",
    "EFTA": "EFTA",
    "SPP": "SPP",
    "EUR1": "EUR1",
}
