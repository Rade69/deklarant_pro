"""
Tool Definitions — definicije alata i system prompt za LLM Tool Use.

Svaki alat odgovara jednoj akciji u Deklarant Pro softveru.
Model (Groq → Gemini kroz LLMProvider) bira alat na osnovu korisnikove poruke.

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
2. Za PRIKAZ (snapshot) stanja taba ili aplikacije → zovi prikazi.
   target: application | invoice | tariffs | origin | items | header | declaration | xml
3. Za PROVJERU/validaciju ("pregledaj", "provjeri", "šta fali", "nedostaje",
   "jesu li ispravne") → zovi provjeri.
   target: application | invoice | tariffs | origin | items | header | declaration | cross_tab | xml
4. Za pretragu tarife po nazivu ili kodu → zovi pretrazi_tarifu
5. Za pretragu porijekla proizvoda → zovi pretrazi_porijeklo
6. Za pronalaženje sličnih proizvoda iz istorije → zovi pronadji_slicne_proizvode
7. Za analizu/upoređivanje tarifa sa istorijom → zovi analiziraj_tarifne
8. Za predlaganje/popunjavanje tarifa za više stavki → zovi predlozi_tarife
9. Za spajanje naimenovanja → zovi spoji_naimenovanja
10. Za upis/ispravku vrijednosti u kolone → zovi upisi_u_kolonu
11. Samo za čisto informativna pitanja NEVEZANA za carinske operacije
    (npr. "šta je carinska tarifa?") možeš odgovoriti direktno bez alata.
12. RAZLIKUJ: "pogledaj/prikaži" (snapshot) od "pregledaj/provjeri" (validacija)!
    • "Prikaži Faktura tab" → prikazi(invoice)
    • "Pregledaj Faktura tab" → provjeri(invoice)
    • "Provjeri naimenovanje 5" → provjeri(items, scope=row, ordinals=[5])
    • "Pokaži naimenovanja" → prikazi(items)
"""

# ── Alati ────────────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "prikazi",
            "description": (
                "Prikazi trenutno stanje (snapshot) trazenog targeta iz aktivnog drafta. "
                "Koristi za: 'pogledaj/pokazi/prikazi tab faktura/naimenovanja/zaglavlje/stanje'. "
                "SAMO za prikaz — NE za provjeru/validaciju."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "enum": ["application", "invoice", "tariffs", "origin", "items", "header", "declaration", "xml"],
                        "description": "Koji dio aplikacije prikazati. Default: application."
                    },
                    "scope": {
                        "type": "string",
                        "description": "all, selection, ili specifičan row broj. Opciono."
                    },
                    "ordinals": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Brojevi redova/stavki (opciono, za scope=row)."
                    }
                },
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "provjeri",
            "description": (
                "Strucna validacija trazenog targeta iz aktivnog drafta. "
                "Koristi za: 'pregledaj/provjeri/validiraj/da li su/sta fali/nedostaje + target'. "
                "Vraca strukturisan nalaz sa blokadama, upozorenjima i preporukama. "
                "NE koristi za prikaz — za to koristi prikazi."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "enum": ["application", "invoice", "tariffs", "origin", "items", "header", "declaration", "cross_tab", "xml"],
                        "description": "Sta validirati. cross_tab = medjutabna uskladenost."
                    },
                    "scope": {
                        "type": "string",
                        "description": "all, selection, ili specifičan row. Opciono."
                    },
                    "ordinals": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Brojevi redova/stavki (opciono)."
                    },
                    "depth": {
                        "type": "string",
                        "enum": ["summary", "full"],
                        "description": "Nivo detalja. summary = zakljucak + blokade. full = svaki nalaz."
                    }
                },
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "pretrazi_tarifu",
            "description": (
                "Pronadji tarifni broj u carinskoj tarifi BiH za dati naziv proizvoda. "
                "NIkADA ne izmisljaj tarifne brojeve napamet."
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
            "name": "pretrazi_porijeklo",
            "description": (
                "Pronadji zemlju porijekla za specifičan proizvod iz istorijskih XML deklaracija."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "naziv": {
                        "type": "string",
                        "description": "Naziv proizvoda za pretragu porijekla"
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
            "name": "pronadji_slicne_proizvode",
            "description": (
                "Pronadji slicne ranije proizvode iz lokalne product similarity memorije "
                "i grupisi rezultate po tarifnom broju."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "naziv": {
                        "type": "string",
                        "description": "Naziv ili opis robe za pretragu slicnih ranijih proizvoda"
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
            "name": "analiziraj_tarifne",
            "description": (
                "Uporedi tarifne brojeve sa istorijom i analiziraj konzistentnost."
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
            "name": "predlozi_tarife",
            "description": (
                "Predlozi tarifne brojeve za stavke koje ih nemaju. "
                "Koristi za batch obradu tarifa za sve stavke bez tarife."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filter": {
                        "type": "string",
                        "description": "Filter keyword za stavke (opciono)."
                    }
                },
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "spoji_naimenovanja",
            "description": "Spoji srodna naimenovanja koja dijele isti tarifni broj, porijeklo i povlasticu.",
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
                "Upisi ili ispravi vrijednost u koloni tabele. "
                "ZAHTIJEVA eksplicitnu potvrdu deklaranta prije izvrsenja."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "kolona": {
                        "type": "string",
                        "description": "Naziv kolone (npr. 'tarifni_broj', 'zemlja_porijekla')"
                    },
                    "vrijednost": {
                        "type": "string",
                        "description": "Nova vrijednost"
                    },
                    "tab": {
                        "type": "string",
                        "description": "Tab u kojem se mijenja (Faktura, Naimenovanja)"
                    }
                },
                "required": ["kolona", "vrijednost"],
                "additionalProperties": False
            }
        }
    },
]
