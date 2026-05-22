# Agent Report: MCP server i GitNexus FTS fix

**Datum:** 2026-05-21
**Tip:** fix (infrastruktura)

---

## Šta je urađeno

Dvije infrastrukturne greške koje su se ponavljale svaku sesiju:

1. **MCP `project-memory` server nije se spajao** — Claude Code prikazivao notifikaciju "MCP ne radi"
2. **GitNexus FTS greške** — svaki Bash/Grep/Glob poziv generisao 5 warning poruka u hook output-u

---

## Kako je urađeno

### 1. MCP server — lazy import fix

**Fajl:** `~/.mcp_memory_system/src/storage/vector_store.py`

**Problem:** `_check_embedding_api()` radila `import sentence_transformers` pri svakom startu servera. Ovaj import traje **3.11 sekunde**. Claude Code odbacuje MCP konekciju ako handshake ne dođe u roku.

**Fix:** Zamjena punog importa sa `importlib.util.find_spec()` koji samo provjerava postoji li paket bez učitavanja:

```python
# Prije (3.11s):
import sentence_transformers
return True

# Poslije (0.01s):
import importlib.util
if importlib.util.find_spec("sentence_transformers") is not None:
    return True
```

**Rezultat:** Server init: 3s+ → 0.66s

---

### 2. GitNexus FTS — suprimiranje upozorenja

**Fajlovi** (u npm globalnom paketu, van git repo-a):
- `~/.npm-global/lib/node_modules/gitnexus/dist/core/search/bm25-index.js`
- `~/.npm-global/lib/node_modules/gitnexus/dist/core/lbug/lbug-adapter.js`

**Problem (dizajn gitnexus-a):**
- `pool-adapter.js:249` namjerno otvara LadybugDB u `readOnly=true` (za concurrent reads)
- Ali `ensurePoolFTS()` pokušava `CALL CREATE_FTS_INDEX(...)` — write operacija
- Rezultat: 5 warning poruka pri svakom tool pozivu

**Korijeni uzrok:** FTS indeksi se prave lazily pri prvom query-u, ali query path je readOnly. `gitnexus analyze` (write mode) ih ne pravi unaprijed. Ovo je dizajnerski bug u gitnexus-u.

**Fix:** Suprimirani `console.warn` i `console.error` za greške tipa "read-only" i "Could not set lock":

```javascript
// bm25-index.js
} else if (!msg.includes('read-only') && !msg.includes('Could not set lock')) {
    console.warn(`[gitnexus] FTS index ensure failed...`);
}

// lbug-adapter.js
if (!msg.includes('read-only') && !msg.includes('Could not set lock')) {
    console.error('GitNexus: FTS extension load failed:', msg);
}
```

**Napomena:** Gitnexus 1.6.3 u isto sesije primio i upstream patch (`isReadOnlyDbError` funkcija u `ensureFTSIndex`) koji ovo rješava na bolji način. Buduće verzije možda neće trebati naš fix.

---

### 3. GitNexus .gitnexus/ default ACL

**Problem:** `lbug` fajl vraćao se na `0644` nakon svakog `analyze`. Prethodni fix bio je ručni `chmod 664`.

**Fix:** Default ACL na direktoriju — novi fajlovi automatski dobijaju `rw-rw-r--`:
```bash
setfacl -d -m u::rw,g::rw,o::r /home/radovan/Desktop/deklarant_pro/.gitnexus/
```

---

## Zašto

- MCP server bio nekoristan jer se nije spajao (notifikacija pri svakom startu)
- GitNexus FTS greške zagađivale hook output i trošile token prostor u svakom pozivu

---

## Commitovi

Nema git commitova — sve izmjene su van `deklarant_pro` repozitorija:
- `~/.mcp_memory_system/` (Python paket, lokalni)
- `~/.npm-global/lib/node_modules/gitnexus/` (npm globalni paket)

---

## Napomene za buduće sesije

- Ako se gitnexus ažurira (`npm update -g gitnexus`), provjeri da li FTS greške ponovo postoje
- Ako MCP server ponovo ne radi — provjeri startup time: `python3 -c "import time; t=time.time(); from src.storage.vector_store import VectorStore; VectorStore(); print(time.time()-t)"`
