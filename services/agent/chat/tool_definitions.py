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
4. Za PRETRAGU/BROJANJE stavki po nazivu ("koliko ima X", "koje stavke sadrže X",
   "nađi sve X", "koliko puta se pojavljuje X") → zovi pretrazi_stavke.
   NIKADA ne broj ručno iz prikazi/provjeri odgovora — to je nepouzdano.
5. Za RAČUNANJE (SUM/AVG/MAX/MIN/COUNT) — "ukupna vrijednost", "koliko ukupno kg",
   "koja stavka ima najveću/najmanju X", "top N", "prosječna X" → zovi agregiraj_stavke.
   NIKADA ne sabiraj/poredi ručno iz prikazi odgovora — to je nepouzdano.
6. Za FILTRIRANJE/GRUPISANJE po polju (tarifa, zemlja, povlastica, faktura,
   prazno/nije prazno) — "koliko stavki nema X", "prikaži sve stavke sa X",
   "da li se X ponavlja" → zovi filtriraj_stavke.
   VAŽNO — target za filtriraj_stavke/agregiraj_stavke: "invoice" = fakturne
   linije (ono što korisnik vidi odmah nakon uvoza fakture, PRIJE kreiranja
   naimenovanja), "items" = naimenovanja (Rb., kreiraju se KASNIJE u toku).
   Ako korisnik NE kaže eksplicitno "naimenovanja"/"Rb." — NE navodi target
   parametar uopšte (izostavi ga), servis će sam odabrati ispravan na osnovu
   toga da li naimenovanja već postoje. NIKAD ne pretpostavljaj "items" kao
   siguran default sam od sebe.
7. Za pretragu tarife po nazivu ili kodu → zovi pretrazi_tarifu
8. Za pretragu porijekla proizvoda → zovi pretrazi_porijeklo
9. Za pronalaženje sličnih proizvoda iz istorije → zovi pronadji_slicne_proizvode
10. Za analizu/upoređivanje tarifa sa istorijom → zovi analiziraj_tarifne
11. Za predlaganje/popunjavanje tarifa za više stavki → zovi predlozi_tarife
12. Za spajanje naimenovanja → zovi spoji_naimenovanja
13. Za upis/ispravku vrijednosti u kolone → zovi upisi_u_kolonu
14. Samo za čisto informativna pitanja NEVEZANA za carinske operacije
    (npr. "šta je carinska tarifa?") možeš odgovoriti direktno bez alata.
15. RAZLIKUJ: "pogledaj/prikaži" (snapshot) od "pregledaj/provjeri" (validacija)!
    • "Prikaži Faktura tab" → prikazi(invoice)
    • "Pregledaj Faktura tab" → provjeri(invoice)
    • "Provjeri naimenovanje 5" → provjeri(items, scope=row, ordinals=[5])
    • "Pokaži naimenovanja" → prikazi(items)
    • "Koliko ima SUSSINA" → pretrazi_stavke(upit="SUSSINA")
    • "Koja je ukupna vrijednost stavki sa tarifom 9405" →
      agregiraj_stavke(operacija="sum", polje="vrijednost", uslovi=[{polje:"tarifa", operator:"=", vrijednost:"9405"}])
    • "Koja stavka ima najveću bruto masu" → agregiraj_stavke(operacija="max", polje="bruto_masa")
    • "Koliko stavki nema zemlju porijekla" (bez pominjanja naimenovanja/Rb.) →
      filtriraj_stavke(uslovi=[{polje:"zemlja", operator:"prazno"}], prikazi="broj")
      — target NIJE naveden namjerno, servis bira invoice/items sam
    • "Koliko naimenovanja nema zemlju porijekla" (eksplicitno "naimenovanja") →
      filtriraj_stavke(target="items", uslovi=[{polje:"zemlja", operator:"prazno"}], prikazi="broj")
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
            "name": "pretrazi_stavke",
            "description": (
                "Precizna, DETERMINISTICKA pretraga i brojanje fakturnih linija i naimenovanja "
                "u aktivnom draftu ciji naziv/opis sadrzi zadati tekst. Koristi UVIJEK za "
                "'koliko ima X', 'koje stavke sadrze X', 'nadji sve X' — vraca tacan broj i "
                "listu, model NE smije sam brojati iz teksta."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "upit": {
                        "type": "string",
                        "description": "Tekst za pretragu (naziv proizvoda ili dio naziva)"
                    },
                    "target": {
                        "type": "string",
                        "enum": ["invoice", "items", "all"],
                        "description": (
                            "Gdje pretraziti: invoice=fakturne linije, items=naimenovanja, "
                            "all=oboje. Default: all."
                        )
                    }
                },
                "required": ["upit"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "agregiraj_stavke",
            "description": (
                "Deterministicki izracunaj SUM/AVG/MAX/MIN/COUNT nad numerickim poljem "
                "fakturnih linija ili naimenovanja u aktivnom draftu, opciono filtrirano. "
                "Koristi UVIJEK za 'ukupna vrijednost', 'koliko ukupno kg', 'koja stavka "
                "ima najvecu/najmanju X', 'top N', 'prosjecna X' — model NIKAD ne racuna sam."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "operacija": {
                        "type": "string",
                        "enum": ["sum", "avg", "max", "min", "count"],
                    },
                    "polje": {
                        "type": "string",
                        "enum": ["vrijednost", "kolicina", "bruto_masa", "neto_masa", "cijena"],
                        "description": "Obavezno osim za operacija=count."
                    },
                    "target": {
                        "type": "string",
                        "enum": ["invoice", "items"],
                        "description": (
                            "invoice=fakturne linije, items=naimenovanja. IZOSTAVI ako "
                            "korisnik ne pominje eksplicitno 'naimenovanja'/'Rb.' — servis "
                            "sam bira ispravan target na osnovu toga da li su naimenovanja "
                            "vec kreirana."
                        )
                    },
                    "uslovi": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "polje": {
                                    "type": "string",
                                    "enum": ["tarifa", "zemlja", "povlastica", "faktura", "naziv"],
                                },
                                "operator": {
                                    "type": "string",
                                    "enum": ["=", "!=", "prazno", "nije_prazno"],
                                },
                                "vrijednost": {"type": "string"},
                            },
                        },
                        "description": "Opcioni filter (AND svih uslova). Npr. tarifa=9405."
                    },
                    "top_n": {
                        "type": "integer",
                        "description": "Za max/min: vrati top N umjesto 1 (npr. 'top 3 najskuplje')."
                    }
                },
                "required": ["operacija"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "filtriraj_stavke",
            "description": (
                "Deterministicki filtriraj i/ili grupisi fakturne linije ili naimenovanja "
                "po bilo kom polju (tarifa, zemlja, povlastica, faktura, prazno/nije prazno). "
                "Koristi za 'koliko stavki nema X', 'prikazi sve stavke sa X', 'da li se X "
                "ponavlja' — model NIKAD ne filtrira/broji sam iz teksta."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "enum": ["invoice", "items"],
                        "description": (
                            "IZOSTAVI ako korisnik ne pominje eksplicitno 'naimenovanja'/"
                            "'Rb.' — servis sam bira ispravan target."
                        )
                    },
                    "uslovi": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "polje": {
                                    "type": "string",
                                    "enum": ["tarifa", "zemlja", "povlastica", "faktura", "naziv"],
                                },
                                "operator": {
                                    "type": "string",
                                    "enum": ["=", "!=", "prazno", "nije_prazno"],
                                },
                                "vrijednost": {"type": "string"},
                            },
                        },
                    },
                    "grupisi_po": {
                        "type": "string",
                        "enum": ["tarifa", "zemlja", "povlastica", "faktura"],
                        "description": "Opciono — grupisi i prebroji po ovom polju (za 'da li se X ponavlja')."
                    },
                    "prikazi": {
                        "type": "string",
                        "enum": ["broj", "listu", "oboje"],
                        "description": "Default: oboje."
                    }
                },
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
