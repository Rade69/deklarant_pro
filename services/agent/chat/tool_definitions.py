"""
Tool Definitions — definicije alata i system prompt za DeepSeek Tool Use.

Svaki alat odgovara jednoj akciji u Deklarant Pro softveru.
Model (DeepSeek) bira alat na osnovu korisnikove poruke.

📄 Povezano: docs/decisions/001-tool-use-refactoring.md
   Zavisnosti: svi servisi u services/agent/ i services/agent/chat/
"""

# ── System Prompt ───────────────────────────────────────────────────
# Vidi: docs/decisions/001-tool-use-refactoring.md#rizici-i-mitigacije

SYSTEM_PROMPT = """\
Ti si carinski agent za Deklarant Pro — softver za carinske deklaracije u BiH.

Tvoj zadatak je da razumiješ korisnikovu namjeru i ODMAH pozoveš odgovarajući alat.

PRAVILA:
1. UVJEK koristi alat za carinske operacije — NIKADA ne izmišljaj tarifne brojeve, 
   podatke ili odgovore napamet.
2. Za upite o tarifnim brojevima → zovi pretrazi_tarifu
3. Za provjeru ispravnosti tarifa → zovi provjeri_tarife
4. Za popunjavanje/predlaganje tarifa za sve stavke → zovi predlozi_tarife
5. Za validaciju cijele deklaracije → zovi validuj_deklaraciju
6. Za pregled naimenovanja → zovi prikazi_naimenovanja
7. Za upis vrijednosti u kolone → zovi upisi_u_kolonu
8. Za spajanje naimenovanja → zovi spoji_naimenovanja
9. Samo za čisto informativna pitanja NEVEZANA za carinske operacije 
   (npr. "šta je carinska tarifa?") možeš odgovoriti direktno bez alata.
10. Za "provjeri tarifne brojeve" ili "jesu li tarife ispravne" → provjeri_tarife (NE validuj_deklaraciju)
11. Za "predloži tarifu za X" (specifičan proizvod) → pretrazi_tarifu (NE predlozi_tarife)
12. Za "predloži tarife" ili "popuni sve" (bez specifičnog proizvoda) → predlozi_tarife
"""

# ── Alati ────────────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "predlozi_tarife",
            "description": (
                "Predloži tarifne brojeve za stavke koje ih nemaju. "
                "Koristi kada korisnik traži da se popune, predlože ili pronađu tarifni brojevi "
                "za sve stavke, za stavke bez tarife, ili batch obradu tarifa. "
                "NE koristi za pretragu tarife za specifičan proizvod — za to koristi pretrazi_tarifu."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filter": {
                        "type": "string",
                        "description": "Filter keyword za stavke (npr. naziv robe). Opciono."
                    }
                },
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "provjeri_tarife",
            "description": (
                "Validiraj ispravnost postojećih tarifnih brojeva u naimenovanjima. "
                "Koristi kada korisnik traži provjeru, validaciju ili pregled ispravnosti "
                "unesenih tarifa. NE koristi za provjeru cijele deklaracije — za to "
                "koristi validuj_deklaraciju."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "pretrazi_tarifu",
            "description": (
                "Pronađi tarifni broj u carinskoj tarifi BiH za dati naziv proizvoda, "
                "materijal ili opis robe. Koristi ZA SVAKI upit o tarifnim brojevima "
                "za specifičan proizvod — NIKADA ne izmišljaj tarifne brojeve napamet."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "naziv": {
                        "type": "string",
                        "description": "Naziv proizvoda, materijala ili robe za pretragu"
                    }
                },
                "required": ["naziv"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "validuj_deklaraciju",
            "description": (
                "Kompletna provjera deklaracije — usklađenost, nedostajuća polja, "
                "greške. Koristi za 'provjeri deklaraciju', 'šta nedostaje', "
                "'compliance check', 'validacija deklaracije'."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "prikazi_naimenovanja",
            "description": (
                "Prikaži pregled svih naimenovanja sa statusom popunjenosti. "
                "Koristi za 'pregledaj naimenovanja', 'pokaži naimenovanja', "
                "'detalji naimenovanja', 'sva naimenovanja'."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "upisi_u_kolonu",
            "description": (
                "Upiši vrijednost u kolonu fakture ili naimenovanja. "
                "Podržane kolone: tarifni broj, zemlja porijekla, povlastica, "
                "procedura (rub.37), pakovanje, oznake, valuta, napomena, itd. "
                "Koristi za 'upiši', 'postavi', 'unesi u kolonu'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "kolona": {
                        "type": "string",
                        "description": "Naziv kolone. Podržano: tarifni broj, zemlja porijekla, povlastica, procedura/rub37, oznake, pakovanje, broj paketa, valuta, napomena, rubrika 40, rubrika 44"
                    },
                    "vrijednost": {
                        "type": "string",
                        "description": "Vrijednost za upis u kolonu"
                    },
                    "tab": {
                        "type": "string",
                        "enum": ["faktura", "naim"],
                        "description": "Tab u koji se upisuje (faktura ili naim). Default: faktura."
                    }
                },
                "required": ["kolona", "vrijednost"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "spoji_naimenovanja",
            "description": (
                "Spoji naimenovanja sa istim tarifnim brojem, zemljom porijekla "
                "i povlasticom. Koristi za 'spoji naimenovanja', 'merge', "
                "'grupiši', 'objedini naimenovanja'."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        }
    },
]
