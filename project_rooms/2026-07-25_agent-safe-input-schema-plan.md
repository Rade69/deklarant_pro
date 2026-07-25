# Plan: Pydantic AgentSafeInput schema za Agent chat kontekst

**Status**: PLAN, nije implementirano. Čeka korisničku odluku o prioritetu
i opsegu prije bilo kakve izmjene koda.

**Povod**: korisnikov dokument "Kontrolisana podatkovna granica za AI
agente" predlaže formalnu Pydantic schemu kao centralnu tačku kroz koju
SVI podaci prema agentu moraju proći (allowlist, ne blocklist). Poređenje
sa stvarnim stanjem (`docs/CONTEXT.md` §61, `agent_reports/2026-07-25_
data-boundary-propust-chat-worker.md`) je otkrilo KONKRETAN propust
(Zone B2 zaobilazila masking iz Zone B) koji je upravo tipa greške koji
formalna schema sprječava strukturno, ne samo zakrpom.

---

## 1. Cilj

Zamijeniti trenutni ad-hoc "string building po zonama" pristup
(`ChatWorker._build_context()` i 6 `_build_*_zone()` metoda koje svaka
posebno odlučuje šta uključiti/maskirati) jednom centralnom, validiranom
strukturom kroz koju MORA proći svako polje prije nego stigne agentu/LLM-u.

Krajnji efekat: nova zona konteksta NE MOŽE ponoviti Zone B2 grešku
(zaboravljen masking) jer masking prestaje biti "nešto što svaka zona mora
sama da uradi" i postaje "nešto što schema/adapter radi automatski za SVE
zone odjednom".

## 2. Trenutno stanje (za referencu)

`gui/tabs/agent/widgets/chat_worker.py::ChatWorker`:

- `_build_context()` (linija 196) — orkestrira 6 zona, spaja ih u JEDAN
  string koji ide u `_build_messages()` → `LLMProvider.complete()/
  stream_chat()`.
- Zone A `db_context` — uvijek uključena, agregatni brojevi (bez tarife/
  zemlje/povlastice), bez partner podataka — već bezbjedna po prirodi.
- Zone B `_build_session_zone()` (linija 659) — partner imena, VEĆ ima
  `_allow_sensitive_data()` gate.
- Zone B2 `_build_zaglavlje_zone()` (linija 474) — zaglavlje polja, SAD
  ima isti gate (fix iz ovog zadatka), ali dodano RUČNO po polju.
- Zone `knowledge`/`tariff_val`/`declarations` — uslovno uključene
  (`_determine_context_zones`), tarifni podaci i istorijske deklaracije;
  `_search_declarations_context` (linija 922) već ima djelimičan
  `send_sensitive` gate za "partner" granu pretrage.
- `TariffLLMWorker._process_batch()` (odvojen fajl, `tariff_llm_worker.py`)
  — POSEBAN, već uzak payload (naziv_robe/product_code/zemlja/kandidati),
  ne prolazi kroz `ChatWorker` zone sistem uopšte.

Zaključak: postoji VIŠE nezavisnih mjesta gdje se odlučuje "šta ide LLM-u",
svako sa svojom logikom. Schema bi ih objedinila.

## 3. Predložena arhitektura

### 3.1 `AgentSafeContext` — Pydantic model po zoni

Umjesto da svaka `_build_*_zone()` vraća `list[str]` (slobodan tekst),
svaka vraća validiran Pydantic model sa EKSPLICITNIM poljima. Primjer:

```python
# services/agent/chat/safe_context_schema.py

from pydantic import BaseModel, Field


class DraftSummary(BaseModel):
    """Zone A — uvijek bezbjedna, samo agregati."""
    total_items: int = Field(ge=0)
    bez_tarife: int = Field(ge=0)
    bez_zemlje: int = Field(ge=0)
    sa_povlasticom: int = Field(ge=0)
    ceka_eur1: int = Field(ge=0)
    zemlja_distribucija: dict[str, int] = {}


class PartnerInfo(BaseModel):
    """Zone B + B2 partner polja — JEDNO mjesto za sve partner podatke.

    `name` je None ako je maskirano (masking se radi PRIJE popunjavanja
    ovog modela, u adapteru — model nikad ne nosi i puno ime i masku
    istovremeno, da se izbjegne greška tipa 'zaboravljen if').
    """
    role: str  # "izvoznik" | "primalac" | "deklarant"
    name: str | None = None
    masked: bool = False


class DeclarationHeaderSummary(BaseModel):
    """Zone B2 preostala (ne-partner) polja."""
    vrsta_deklaracije: str = ""
    carinska_ispostava: str = ""
    valuta: str = ""
    iznos: float = 0.0
    kurs: float = 1.0
    uslovi_isporuke: str = ""
    vid_transporta: str = ""
    drzava_izvoza: str = ""
    troskovi: list[str] = []
    # header_attached_documents namjerno IZOSTAVLJENO dok se ne odluči
    # da li su brojevi dokumenata osjetljivi (vidi §7 otvorena pitanja)


class AgentSafeContext(BaseModel):
    """Kompletan kontekst koji ide agentu — JEDINA tačka validacije."""
    draft_summary: DraftSummary
    partners: list[PartnerInfo] = []
    header: DeclarationHeaderSummary | None = None
    # knowledge/tariff_val/declarations zone ostaju kao dodatne, opcione
    # liste stringova ZA SADA (vidi §6 — postepena migracija)
    knowledge_context: list[str] = []
    tariff_validation_context: list[str] = []
    declarations_context: list[str] = []
```

### 3.2 `AgentContextAdapter` — jedina tačka maskiranja

```python
# services/agent/chat/context_adapter.py

class AgentContextAdapter:
    """Jedina tačka kroz koju draft podaci postaju AgentSafeContext.

    Maskiranje se radi OVDJE, jednom, za sva partner polja — ne po zoni.
    """

    def __init__(self, draft, allow_sensitive: bool):
        self.draft = draft
        self.allow_sensitive = allow_sensitive

    def build_partner_info(self) -> list[PartnerInfo]:
        pairs = [
            ("izvoznik", getattr(self.draft, "izvoznik_naziv", "")),
            ("primalac", getattr(self.draft, "primalac_naziv", "")),
            ("deklarant", getattr(self.draft, "deklarant_naziv", "")),
        ]
        result = []
        for role, name in pairs:
            if not name:
                continue
            result.append(PartnerInfo(
                role=role,
                name=name if self.allow_sensitive else None,
                masked=not self.allow_sensitive,
            ))
        return result

    # ... build_draft_summary(), build_header() analogno
```

### 3.3 Renderovanje nazad u tekst za LLM

LLM i dalje prima tekst (Groq/Gemini API-ji ne uzimaju strukturisan JSON
kontekst) — ali se tekst SAD generiše iz VEĆ VALIDIRANOG `AgentSafeContext`
objekta, na jednom mjestu (`render_to_prompt_text()`), ne u svakoj zoni
posebno. Time se maskiranje ne može zaobići pri renderovanju jer
`PartnerInfo.name` je već `None` prije nego što stigne do render koraka.

## 4. Šta se NE mijenja (scope lock)

- `LLMProvider`, Groq/Gemini poziv sam po sebi — netaknuto.
- `TariffLLMWorker` payload (već uzak, već ispravan) — ostaje kako jeste,
  MOŽDA kasnije migrira na istu shemu radi konzistentnosti, ali nije
  prioritet (nema poznat propust tamo).
- `HistoricalTariffSearchService`, `TariffMappingService` i ostali servisi
  koji NE grade LLM prompt — netaknuto.
- Poslovna logika izračuna (tarife, težine, validacije) — netaknuto,
  schema samo mijenja KAKO se podaci pakuju za agenta, ne šta aplikacija
  interno radi.

## 5. GitNexus impact (procjena prije bilo kakve izmjene)

`_build_context()` je centralna metoda `ChatWorker`-a — realno OČEKIVATI
HIGH/CRITICAL GitNexus impact (ista situacija kao `_update_status_bar` u
§60, čvorna funkcija). **Prije stvarne implementacije, obavezno ponovo
pokrenuti `gitnexus_impact` na `_build_context` i sve `_build_*_zone`
metode, napisati/ažurirati project_room sa tačnim brojevima, i prijaviti
korisniku PRIJE izmjene** — ovaj plan fajl NIJE zamjena za taj korak, samo
priprema.

## 6. Predložena postepena migracija (ne big-bang)

Big-bang prepisivanje `_build_context()` odjednom je rizično (6 zona, 1199
linija fajl, HIGH impact). Predlog faza:

1. **Faza 1** — dodati `safe_context_schema.py` i `context_adapter.py` kao
   NOVE fajlove, BEZ dirat postojeći `chat_worker.py`. Napisati testove za
   adapter izolovano (schema validacija, masking logika) — nula rizika za
   postojeći kod.
2. **Faza 2** — migrirati SAMO Zone B + Zone B2 (partner polja — tačno
   mjesto gdje je propust nađen) da koriste `AgentContextAdapter.
   build_partner_info()` + render umjesto ručnog `if send_sensitive:` po
   polju. Regresioni testovi (postojeći iz §61 + novi) moraju proći
   identično.
3. **Faza 3** — migrirati `DraftSummary` (Zone A) — niskorizično, već
   bezbjedno, samo strukturno.
4. **Faza 4** — migrirati `DeclarationHeaderSummary` (ostatak Zone B2).
5. **Faza 5 (opciono, veći rizik)** — `knowledge`/`tariff_val`/
   `declarations` zone — ove imaju najviše ad-hoc logike (RAG kandidati,
   istorijska pretraga), najveći posao, najmanja hitnost (nema poznat
   propust). Zasebna odluka da li se uopšte radi.

Svaka faza — zaseban commit, zaseban test run, zaseban `gitnexus_detect_
changes()`.

## 7. Otvorena pitanja za korisnika (prije Faze 1)

- ~~Da li `header_attached_documents` (Rb.44, brojevi priloženih isprava —
  npr. EUR.1 broj) treba tretirati kao osjetljivo?~~ **ODGOVORENO
  (2026-07-25): NE — brojevi priloženih isprava nisu relevantni i ne
  trebaju se maskirati.** `DeclarationHeaderSummary` u §3.1 ostaje bez tog
  polja (već izostavljeno), potvrđeno kao namjerno, ne privremeno.
- Da li migracija ide do Faze 5 (sve zone) ili staje na Fazi 4 (partner +
  header polja, gdje je i nađen stvaran propust)?
- Da li `TariffLLMWorker` treba migrirati na istu shemu radi
  konzistentnosti, iako trenutno nema poznat propust?
- Prioritet u odnosu na ostale otvorene stavke (§57-60 iz CONTEXT.md,
  Codex/Pi nalazi 3a/2b/5a) — da li ovo ide prije ili poslije njih?

## 8. Testiranje (forbidden-marker pristup iz dokumenta §12)

Uz migraciju, dodati jedan generalizovan test:

```python
FORBIDDEN_MARKERS = [
    "SECRET_API_KEY_SHOULD_NOT_LEAK",
    "EXPORTER_NAME_SHOULD_NOT_LEAK",
    "CONSIGNEE_JIB_SHOULD_NOT_LEAK",
]

def test_build_context_ne_curi_markere_kad_je_sensitive_iskljucen():
    """Ubaci markere u draft, provjeri da se NIJEDAN ne pojavi u
    _build_context() outputu kad je SEND_SENSITIVE_DATA=false."""
    ...
```

Ovo bi uhvatilo BAŠ propust iz §61 automatski, umjesto da čeka na ručno
poređenje sa eksternim dokumentom.

## 9. Procjena obima (informativno, ne obavezujuće)

- Faza 1: ~2-3h (novi fajlovi, izolovani testovi).
- Faza 2: ~2-3h (migracija + regresioni testovi + dist_client mirror).
- Faza 3-4: ~1-2h svaka.
- Faza 5: nepoznato dok se ne analiziraju sve tri preostale zone pojedinačno
  — mogao bi biti veći od svih prethodnih faza zajedno.

## 10. Zaključak

Plan je namjerno postepen i zaustaviv nakon svake faze — matches AGENTS.md
princip "Plan prije izmjene" za HIGH-impact simbole i korisnikovu opštu
sklonost ka malim, provjerljivim koracima umjesto velikog refaktora
odjednom. Faza 1-2 (partner polja) direktno rješava STRUKTURNI uzrok
propusta iz §61, ne samo simptom.
