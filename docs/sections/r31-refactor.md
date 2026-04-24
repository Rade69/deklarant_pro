# Rb.31 — Pakovanje i opis robe (refaktor)

## Datum
2026-04-23

## Razlog
Korisnik je uočio da u ASYCUDA World aplikaciji više nema kontejner polja (`Container_number`) na poziciji Rb.31. Takođe, redoslijed prikaza opisa tarife (heading vs podbroj) nije odgovarao željenom redoslijedu prilikom bildanja XML deklaracije.

## Sta je uradjeno

### 1. Uklonjena kontejner polja iz Rb.31
Izbrisana su polja:
- `le_r31_kontejner_1` (QLineEdit)
- `le_r31_kontejner_2` (QLineEdit)
- `lbl_r31_kontejner` (QLabel "Kontejner")

jer ih u ASYCUDA World aplikaciji više nema na tom mjestu.

**Fajlovi:**
- `ui/naimenovanja_tab_OPTIMIZED.ui` — uklonjeni widgeti iz `group_31`
- `ui/naimenovanja_tab_OPTIMIZED_ui.py` — uklonjene generisane Python reference
- `gui/tabs/naimenovanja_view.py` — uklonjeno iz `field_map` i `order` liste
- `gui/tabs/naimenovanja_controller.py` — uklonjeno `container_number1/2` iz default item inicijalizacije i `items_data` dump-a
- `gui/tabs/agent/services/chat_intent_handler.py` — uklonjen red "Kontejneri:" iz HTML pregleda naimenovanja
- `gui/widgets/smart_buttons.py` — ispravljen `_fill_from_packing` da čita broj i vrstu paketa iz ispravnih polja (`le_r31_broj`, `le_r31_vrsta_naziv`) umjesto iz kontejner polja

### 2. Zamijenjen sadržaj te_r31_opis i te_r31_opis_2
Ranije je `te_r31_opis` (gornje polje) prikazivao heading opis (4-6 cifara, viši nivo), a `te_r31_opis_2` (donje polje) prikazivao opis podbroja (8-10 cifara, tačan broj).

Zamijenjeno je tako da:
- **`te_r31_opis`** (gore, y=98) — prikazuje **opis podbroja** (8-10 cifara, npr. "16010099"), **zelena boja** (`#e8f5e8`, border `#4caf50`)
- **`te_r31_opis_2`** (dolje, y=125) — prikazuje **heading opis** (4-6 cifara, npr. "1601"), **plava boja** (`#e3f2fd`, border `#2196f3`) — ista boja kao `le_r31_vrsta_naziv`

Razlog: korisnik želi da se prilikom bildanja XML deklaracije u `<Goods_description>` prvo upiše `Description_of_goods` (podbroj, precizan opis), zatim `Commercial_Description` (heading opis + trgovački nazivi iz fakture). XML builder je već generisao tim redoslijedom i nije mijenjan.

### 3. Sta nije mijenjano
- **`NaimenovanjeDraft` model** (`core/draft/draft.py`) — `container_number1/2` i dalje postoje u modelu radi XML importa
- **`zaglavlje_service.py`** — XML parser i dalje čita kontejner podatke iz uvezenih XML fajlova
- **`asycuda_xml_builder.py`** — nije mijenjan, redoslijed u `<Goods_description>` je ispravan
- **Testovi** — nisu mijenjani, postojeći testovi i dalje testiraju `container_number1` u modelu

## Layout Rb.31 (nakon izmjena)

```
┌──────────────────────────────────────────────────────────────────┐
│ 31 Pakovanje i          Oznake i brojevi - broj vrsta pakata    │
│ opis robe               ┌────────────────────────────────────┐   │
│                         │ le_r31_oznake_br                   │   │
│                         └────────────────────────────────────┘   │
│          Oz.i br.pakata ┌────────────────────────────────────┐   │
│                         │ le_r31_paketa                      │   │
│                         └────────────────────────────────────┘   │
│          Broj i vrsta   ┌──┐┌──┐┌────────────────────────────┐   │
│                         │br││šf││ le_r31_vrsta_naziv (plavo) │   │
│                         └──┘└──┘└────────────────────────────┘   │
│                         ┌────────────────────────────────────┐   │
│  (gore, zeleno)         │ te_r31_opis (podbroj 8-10 cif)    │   │
│                         └────────────────────────────────────┘   │
│                         ┌────────────────────────────────────┐   │
│  (dole, plavo)          │ te_r31_opis_2 (heading 4-6 cif)   │   │
│                         └────────────────────────────────────┘   │
│                         ┌────────────────────────────────────┐   │
│                         │ le_r31_trg_naziv (QTextEdit)      │   │
│                         │  auto-expand, max 550 zn          │   │
│                         └────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

## Struktura XML-a (<Goods_description>)

Redoslijed u izgenerisanom XML fajlu:

```xml
<Goods_description>
  <Country_of_origin_code>MK</Country_of_origin_code>
  <Country_of_origin_region><null /></Country_of_origin_region>
  <Description_of_goods>- - ostalo</Description_of_goods>
  <Commercial_Description>Kobasice i sl.proizvodi od mesa
ŠUNKA,PICA ŠUNKA,SRPSKA,ROŠTILJSKA...</Commercial_Description>
</Goods_description>
```

Gdje je:
- `Description_of_goods` ← `tariff_description1` (te_r31_opis, podbroj, zeleno)
- `Commercial_Description` ← `tariff_description2` (te_r31_opis_2, heading, plavo) + `goods_trade_name` (le_r31_trg_naziv)

## Verzija
Commit: `dbf5664`
Branch: `dev` (spojen na `main`)
