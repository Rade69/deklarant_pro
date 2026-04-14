# Prijedlog: interna privatna AI coding platforma sa lokalnim LLM modelima

**Namjena dokumenta:** interni prijedlog za firmu sa ~10+ programera i 2–3 dizajnera koja želi AI pomoć u kodiranju bez slanja izvornog koda i internih informacija velikim cloud LLM servisima.

**Datum:** 2026-04-13

---

## 1. Sažetak za menadžment

Za tim ove veličine ne preporučuje se pristup **"jedan ogroman model za sve"**. Razumniji pristup je izgradnja **privatne interne AI platforme** sa:

1. **brzim modelom** za svakodnevne coding zadatke,
2. **jačim modelom** za složeniji refaktor, code review i arhitekturna pitanja,
3. **lokalnim retrieval slojem (RAG)** za internu dokumentaciju, standarde, runbook-ove i repozitorije.

Ovakva arhitektura je praktičnija, jeftinija i lakše prihvatljiva timu od pokušaja da se odmah gradi ili trenira jedan veliki "vlastiti LLM".

---

## 2. Ciljevi sistema

Predloženi sistem treba da omogući:

- privatnu upotrebu AI-a bez slanja koda van firme,
- pomoć u pisanju i razumijevanju koda,
- generisanje testova, SQL upita i dokumentacije,
- code review uz interna pravila firme,
- pretragu interne dokumentacije i objašnjenja na osnovu lokalnih izvora,
- auditabilan i kontrolisan pristup po korisniku/timu/projektu.

---

## 3. Preporučena arhitektura

### 3.1. Pregled arhitekture

```text
[VS Code / JetBrains / Terminal alati]
                |
                v
      [Interni API Gateway + Auth]
                |
      -----------------------------
      |            |             |
      v            v             v
 [Fast model] [Deep model] [RAG / Knowledge Layer]
      |            |             |
      -----------------------------
                |
                v
      [Logging / Audit / Metrics]
```

### 3.2. Slojevi

#### A. Inference sloj

Preporučeni engine je **vLLM** kao glavni inference server, jer nudi **OpenAI-compatible API** i praktičan je za integraciju sa alatima koji već očekuju OpenAI stil endpointa. To omogućava da interni modeli budu dostupni kao standardni API bez zaključavanja za jednog vendora.

**Zašto vLLM:**
- OpenAI-compatible server,
- prikladan za timsku upotrebu,
- podrška za ozbiljniji produkcioni serving,
- podrška za različite hardverske platforme uključujući NVIDIA i AMD GPU-ove.

**Napomena:** za vrlo jednostavan pilot može se koristiti i **Ollama**, ali ga ne preporučujem kao glavni produkcioni sloj za firmu sa 10+ developera.

#### B. Klijentski sloj

Preporučujem dvije vrste klijenata:

- **Aider** za terminalski način rada i rad direktno nad git repozitorijima,
- **Cline** ili sličan IDE agent za VS Code / editor integracije.

Bitno je da i Aider i Cline podržavaju **OpenAI-compatible API** pristup, pa se mogu povezati na interni lokalni model server bez potrebe za cloud provajderom.

#### C. Retrieval / knowledge sloj

Za internu dokumentaciju i pretragu znanja preporuka je:

- **Qdrant** ako se želi čist i brz vektorski retrieval sistem,
- **pgvector** ako firma već snažno koristi PostgreSQL i želi zadržati vektorske podatke uz postojeći DB ekosistem.

**Qdrant prednost:** čist fokus na vector search i RAG.

**pgvector prednost:** vektori ostaju u PostgreSQL-u, uz ACID, point-in-time recovery i jednostavniji operativni model za timove koji već žive u PostgreSQL svijetu.

#### D. Sigurnosni sloj

Obavezan je dodatni sloj ispred model servera:

- interni reverse proxy,
- autentikacija (idealno SSO/LDAP, ili makar API ključevi + interni korisnički nalozi),
- logging i audit,
- rate limiting,
- segmentacija pristupa po projektu ili timu.

Ovo je posebno važno zato što Qdrant u self-hosted načinu **po defaultu nije siguran**, a bez dodatne zaštite i neki drugi lokalni servisi mogu ostati nepotrebno izloženi.

---

## 4. Preporučeni modeli

### 4.1. Glavni kandidat za coding

#### Opcija A — Qwen3-Coder

Qwen3-Coder je vrlo ozbiljan kandidat za internu coding platformu jer je pozicioniran upravo za coding i agentic coding scenarije.

**Preporučena upotreba:**
- generisanje i objašnjavanje koda,
- refaktor manjih i srednjih cjelina,
- pisanje testova,
- pomoć pri razumijevanju većih repozitorija,
- interni coding agent zadaci.

#### Opcija B — DeepSeek-Coder-V2-Lite / V2

DeepSeek-Coder-V2-Lite je dobar kandidat za **brži lane** i troškovno efikasniji coding assist. Puna V2 varijanta je mnogo zahtjevnija i ne bih je preporučio kao prvu produkcionu opciju za tim ove veličine.

**Preporučena upotreba:**
- brze dnevne coding asistencije,
- generisanje pomoćnog koda,
- kratki refaktori,
- brza interaktivna pomoć u editoru.

### 4.2. Strategija modela

Najbolja početna strategija nije jedan model, nego:

- **Fast lane model**: brzi coding assist,
- **Deep lane model**: složeniji review, refaktor i arhitektura,
- **RAG endpoint**: isti ili jači model, ali sa internim dokumentima i pravilima firme u kontekstu.

---

## 5. Kako to organizovati u praksi

### Servis 1 — Fast Coding Assistant

Namjena:
- generisanje funkcija,
- autocomplete / nastavak koda,
- objašnjenja manjih blokova,
- generisanje testova,
- brzi SQL / regex / utility zadaci.

Cilj:
- odgovor u rasponu od približno 2–5 sekundi za tipične zahtjeve.

### Servis 2 — Deep Coding / Review Assistant

Namjena:
- analiza više fajlova,
- složeniji refaktori,
- arhitekturna pitanja,
- code review po internim pravilima,
- pomoć oko migracija i debug sesija.

### Servis 3 — Internal Knowledge Assistant

Namjena:
- pretraga tehničke dokumentacije,
- objašnjenje internih standarda,
- onboarding pomoć,
- Q&A nad API specifikacijama, wiki sadržajem, ADR dokumentima i runbook-ovima.

---

## 6. Hardverske preporuke

Ovdje treba biti vrlo direktan:

Za tim od 10+ developera **nije realno** očekivati dobro iskustvo sa jednim običnim desktop računarom i 24 GB VRAM-a. Problem nije samo da model "stane", nego da sistem ostane upotrebljiv kada više ljudi radi paralelno.

### 6.1. Minimum ozbiljnog pilota

**Varijanta A**
- 1 × GPU sa **96 GB VRAM**
- 256 GB RAM
- 2–4 TB NVMe
- Linux server

**Kada ima smisla:**
- pilot,
- manji broj istovremenih korisnika,
- evaluacija prije veće kupovine.

### 6.2. Preporučeni balans za timsku produkciju

**Varijanta B**
- 2 × GPU sa **48 GB VRAM**
- 256–512 GB RAM
- 2 × NVMe (po mogućnosti mirror za sistem i modele)
- Linux server / workstation-server konfiguracija

**Kada ima smisla:**
- ozbiljan početak za firmu ove veličine,
- odvojeni fast i deep workload,
- bolji paralelizam i fleksibilnost.

### 6.3. Premium varijanta

**Varijanta C**
- 2 × GPU sa **96 GB VRAM**
- 512 GB RAM
- enterprise NVMe storage
- redundantno napajanje ako ide u ozbiljniji server format

**Kada ima smisla:**
- više paralelnih korisnika,
- dugoročniji rast,
- potreba za većim modelima i većim kontekstima,
- više projekata i više timova na istoj platformi.

---

## 7. Aktuelne cijene hardvera (orijentaciono)

> **Važno:** enterprise GPU cijene često zavise od regiona, resellera, poreza i dostupnosti. Ispod su navedene **javne objavljene cijene** i **primjeri tržišnih cijena** dostupni na dan 2026-04-13.

### 7.1. NVIDIA RTX 6000 Ada Generation (48 GB ECC)

- **Zvanično objavljena cijena na NVIDIA Marketplace-u:** **USD 6,800**
- **Primjer EU retail / reseller cijene:** **EUR 8,587.43** (Instar Informatika)

**Šta to znači za projekat:**
- 1 × RTX 6000 Ada = oko **USD 6,800**
- 2 × RTX 6000 Ada = oko **USD 13,600** samo za GPU dio platforme

Ova kartica je ozbiljan kandidat za balansiranu lokalnu inference platformu, ali treba imati u vidu da **nema NVLink**, pa se ne treba oslanjati na staru logiku "spajanja memorije" kakva je nekad bila popularna.

### 7.2. NVIDIA RTX PRO 6000 Blackwell Workstation Edition (96 GB ECC)

- **Zvanično objavljena cijena na NVIDIA Marketplace-u:** **USD 8,900**

**Šta to znači za projekat:**
- 1 × RTX PRO 6000 Blackwell = oko **USD 8,900**
- 2 × RTX PRO 6000 Blackwell = oko **USD 17,800** samo za GPU dio platforme

Ovo je trenutno znatno jača i dugoročnije sigurnija opcija za ozbiljan lokalni AI server.

### 7.3. Cloud kao pilot alternativa

Ako firma ne želi odmah CAPEX kupovinu, postoji i opcija da se pilot prvo uradi u kontrolisanom okruženju na iznajmljenom GPU-u.

Primjer za **RTX 6000 Ada cloud**:
- oko **USD 0.39–1.57 / sat**,
- odnosno približno **USD 280.80–1,130.40 / mjesec** po GPU-u ako se koristi 720 sati mjesečno.

**Zaključak:** cloud pilot može biti razuman za kratki dokaz koncepta, ali za stalnu internu upotrebu i privatnost lokalni server ostaje smislenija dugoročna opcija.

---

## 8. Procjena investicije po nivoima

### Opcija 1 — Pilot

**Cilj:** validacija prije veće kupovine.

**Predlog:**
- 1 × 96 GB GPU server
- ili kratki cloud pilot

**Raspon ulaganja:**
- ako se kupuje samo GPU osnova: oko **USD 8,900** za GPU,
- uz ostatak platforme (CPU, RAM, NVMe, kućište/server, napajanje, hlađenje) realno treba očekivati **značajno više**.

> **Praktična napomena:** potpuna cijena servera zavisi od odabira platforme i dobavljača, pa se za finalnu CAPEX procjenu mora tražiti konkretna ponuda integratora. GPU javne cijene su dobar minimum za planiranje, ali nisu kompletna serverska cijena.

### Opcija 2 — Balanced produkcija

**Predlog:**
- 2 × RTX 6000 Ada 48 GB

**Orijentacioni minimum za GPU dio:**
- oko **USD 13,600**

**Najveća prednost:**
- dobar odnos cijene i ozbiljnosti,
- pristojan ulaz za timsku upotrebu,
- razdvajanje fast i deep workload-a.

### Opcija 3 — Premium produkcija

**Predlog:**
- 2 × RTX PRO 6000 Blackwell 96 GB

**Orijentacioni minimum za GPU dio:**
- oko **USD 17,800**

**Najveća prednost:**
- duži vijek rješenja,
- više prostora za veće modele i više korisnika,
- manje potrebe za ranim upgrade-om.

---

## 9. Šta ne preporučujem

Ne preporučujem sljedeće pristupe kao glavno rješenje za tim ove veličine:

- jedan običan desktop sa 24 GB VRAM-a kao centralni server za cijeli tim,
- CPU-only inference server,
- pokušaj treniranja vlastitog velikog modela od nule,
- kupovinu hardvera prije nego što se definišu stvarni workload-i,
- oslanjanje samo na jedan veliki model za sve scenarije.

Razlog je jednostavan: takva rješenja često djeluju jeftinije na početku, ali vrlo brzo postanu usko grlo i korisnici ih prestanu koristiti.

---

## 10. Preporučeni fazni plan implementacije

### Faza 1 — Pilot (2–4 sedmice)

- postaviti 1 interni inference server,
- testirati 2–3 modela,
- uključiti 4–5 developera kao pilot grupu,
- definisati 20–30 stvarnih zadataka iz njihove svakodnevice,
- mjeriti kvalitet, latenciju, greške i prihvaćenost.

### Faza 2 — RAG i interna baza znanja

- indeksirati dokumentaciju,
- indeksirati API opise, wiki, standarde i runbook-ove,
- odvojiti namespace-ove / tenant logiku po projektu ili timu,
- ograničiti pristup osjetljivim kolekcijama.

### Faza 3 — Guardrails i pravila firme

- system prompt po firmi,
- coding style i naming pravila,
- sigurnosna pravila,
- pravila za testove i commit poruke,
- politika pristupa po korisniku i timu.

### Faza 4 — Dodatna optimizacija

Tek nakon stvarne upotrebe ima smisla razmišljati o:
- LoRA/fine-tuning prilagođavanju,
- boljem model routing-u,
- specijalizovanom prompt engineering-u po timu,
- evaluacionom framework-u i benchmark-u nad internim zadacima.

---

## 11. Konačna preporuka

Za firmu sa oko 10+ programera i 2–3 dizajnera preporučujem da ovo **ne prodaje kao "pravljenje vlastitog LLM-a"**, nego kao:

> **Privatna interna AI coding platforma sa lokalnim modelima i potpunom kontrolom podataka.**

### Najracionalniji početni izbor

**Softver / stack:**
- vLLM kao inference server,
- Open WebUI kao interni web interfejs,
- Aider i/ili Cline kao radni klijenti,
- Qdrant ili pgvector za retrieval sloj,
- interni auth + audit + proxy.

**Model strategija:**
- Qwen3-Coder kao glavni kandidat,
- DeepSeek-Coder-V2-Lite kao brži kandidat,
- po potrebi jedan jači model ili routing za kompleksnije zadatke.

**Hardver:**
- za ozbiljan start: **2 × 48 GB GPU** ili **1 × 96 GB GPU**,
- za dugoročnije i komfornije rješenje: **2 × 96 GB GPU**.

### Moj praktični zaključak

Ako je cilj ponuditi firmi nešto što je **stvarno korisno, privatno i održivo**, najbolji put je:

1. mali pilot,
2. mjerenje stvarnih rezultata,
3. tek onda kupovina punog produkcionog sistema.

To je mnogo jači pristup od velikih obećanja o "vlastitom modelu", jer menadžmentu i timu zapravo treba **alat koji ubrzava rad i ne iznosi podatke iz firme**.

---

## 12. Izvori

1. Qwen3-Coder GitHub: https://github.com/QwenLM/Qwen3-Coder
2. DeepSeek-Coder-V2 Instruct: https://huggingface.co/deepseek-ai/DeepSeek-Coder-V2-Instruct
3. DeepSeek-Coder-V2 kolekcija: https://huggingface.co/collections/deepseek-ai/deepseekcoder-v2
4. vLLM OpenAI-compatible server: https://docs.vllm.ai/en/stable/serving/openai_compatible_server/
5. vLLM quickstart: https://docs.vllm.ai/en/latest/getting_started/quickstart/
6. Open WebUI docs: https://docs.openwebui.com/
7. Open WebUI offline mode: https://docs.openwebui.com/tutorials/maintenance/offline-mode/
8. Aider OpenAI-compatible docs: https://aider.chat/docs/llms/openai-compat.html
9. Cline OpenAI-compatible docs: https://docs.cline.bot/provider-config/openai-compatible
10. pgvector GitHub: https://github.com/pgvector/pgvector
11. Qdrant security docs: https://qdrant.tech/documentation/operations/security/
12. Qdrant quickstart: https://qdrant.tech/documentation/quickstart/
13. Qdrant multitenancy docs: https://qdrant.tech/documentation/manage-data/multitenancy/
14. NVIDIA RTX 6000 Ada Generation Marketplace page: https://marketplace.nvidia.com/en-us/enterprise/laptops-workstations/nvidia-rtx-6000-ada-generation/
15. NVIDIA RTX PRO 6000 Blackwell Workstation Edition Marketplace page: https://marketplace.nvidia.com/en-us/enterprise/laptops-workstations/nvidia-rtx-pro-6000-blackwell-workstation-edition/
16. Instar Informatika RTX 6000 Ada listing: https://www.instar-informatika.hr/graficka-pny-nvidia-rtx6000-ada-48gb-gddr6-ecc/154791/product/
17. NVIDIA RTX 6000 product page: https://www.nvidia.com/en-us/products/workstations/rtx-6000/
18. RTX 6000 Ada cloud pricing comparison: https://getdeploying.com/gpus/nvidia-rtx-6000-ada
