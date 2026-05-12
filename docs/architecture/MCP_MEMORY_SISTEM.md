**MCP Memory Sistem — Kako radi**  
**Šta je to, jednom rečenicom**  
Svaki AI agent (Claude, Qwen, Cline, Codex...) može da upiše i pročita znanje o projektu kroz jedan centralni sistem, umjesto da svaki agent počinje od nule.  
![](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAnEAAAACCAYAAAA3pIp+AAAABmJLR0QA/wD/AP+gvaeTAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAAMUlEQVR4nO3WAQkAIBAEsBPMYs4PZhMDWMAA5njYUmxU1UqyAwBAF2cmeZE4AIBO7gentgXapSWpbgAAAABJRU5ErkJggg==)  
**Problem koji rješava**  
Kada otvoriš novi chat sa Claude-om (ili bilo kojim agentom), agent ne pamti ništa iz prethodnih sesija. Svaki put moraš objašnjavati kontekst projekta iznova.  
**Staro rješenje:** Flat .md fajlovi u ~/.claude/projects/.../memory/ — funkcioniše, ali samo Claude Code ih čita automatski. Qwen, Cline i drugi agenti nemaju pristup.  
**Novo rješenje:** MCP server koji svi agenti pozivaju na isti način.  
![](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAnEAAAACCAYAAAA3pIp+AAAABmJLR0QA/wD/AP+gvaeTAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAANElEQVR4nO3OUQmAABBAsSdYxKYXx1gmEBOIFfwTYUuwZWa2ag8AgL841uquzq8nAAC8dj05WgYLQTzjnAAAAABJRU5ErkJggg==)  
**Kako izgleda u praksi**  
Ti otvoriš novi chat sa Claude-om  
         │  
 Claude automatski poziva:  
   get_project_context(project_id="deklarant_pro")  
         │  
         ▼  
 Dobija: opis projekta, zadnje odluke, poznati bugovi, pravila  
         │  
         ▼  
 Claude već zna kontekst bez da mu išta objašnjavaš  
   
Na kraju sesije, agent može da upiše šta je naučio:  
save_session_summary(project_id="deklarant_pro", ...)  
         │  
         ▼  
 Sljedeći agent (ili sljedeća sesija) može da pročita  
   
![](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAnEAAAACCAYAAAA3pIp+AAAABmJLR0QA/wD/AP+gvaeTAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAANUlEQVR4nO3OMQ2AABAAsSNhZscVjnidKEAGFtgISaugy8zs1RkAAH9xr9VWHV9PAAB47XoAor8EPg1yCpUAAAAASUVORK5CYII=)  
**Gdje živi sve**  
~/.mcp_memory_system/          ← root servera  
 Preporučujem da obrišem asycuda_pro zapise iz baze i stari folder. Da li da to uradim?Preporučujem da obrišem asycuda_pro zapise iz baze i stari folder. Da li da to uradim?├── run_server.py              ← ovo se pokreće kao MCP server  
 ├── configs/  
 │   └── main_config.yaml       ← konfiguracija (baza, logovi...)  
 └── src/  
     ├── mcp/  
     │   └── memory_mcp_server.py   ← definicija 9 alata  
     ├── core/  
     │   └── memory_system.py       ← business logika  
     └── storage/  
         └── postgres_storage.py    ← čita/piše u bazu  
   
 Baza podataka: PostgreSQL, lokalna, baza se zove "mcp_memory"  
 Tabele: projects, memory_records, audit_log  
   
![](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAnEAAAACCAYAAAA3pIp+AAAABmJLR0QA/wD/AP+gvaeTAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAANUlEQVR4nO3OQQmAABRAsSeYxKS/kJkED6bwYAVvImwJtszMVu0BAPAXx1rd1fn1BACA164HHDwF+DpPyKwAAAAASUVORK5CYII=)  
**9 alata koje agenti mogu koristiti**  
| | | |  
|-|-|-|  
| **Alat** | **Šta radi** | **Kada se koristi** |   
| get_project_context | Vraća sve o projektu odjednom | Na početku svake sesije |   
| search_project_memory | Pretražuje znanje po ključnoj riječi | Kad treba specifična info |   
| save_session_summary | Snima šta je urađeno u sesiji | Na kraju sesije |   
| save_decision | Snima arhitektonsku odluku | Kad se donese važna odluka |   
| get_recent_decisions | Liste zadnjih odluka | Za pregled historije |   
| get_known_issues | Lista poznatih bugova/izuzetaka | Prije rada na srodnoj oblasti |   
| get_project_rules | Pravila specifična za projekat | Kad agent ne zna standard |   
| get_global_rules | Pravila koja važe za sve projekte | Opšta pravila rada |   
| cross_project_search | Pretražuje više projekata | Rijetko, za poređenje |   
   
![](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAnEAAAACCAYAAAA3pIp+AAAABmJLR0QA/wD/AP+gvaeTAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAANElEQVR4nO3OQQmAABRAsaeILbwZ9Fewo0Gs4E2ELcGWmTmqKwAA/uLeqr06v54AAPDa+gAthwNEfGhnhAAAAABJRU5ErkJggg==)  
**Tipovi znanja koje možeš snimiti**  
| | |  
|-|-|  
| **Tip** | **Primjer** |   
| session_summary | "Danas smo popravili Rub.36/Rub.44 bug" |   
| decision | "Koristimo TariffFacade umjesto direktnih servisa" |   
| rule | "SQL upiti uvijek sa psycopg2.sql, nikad f-string" |   
| fact | "PostgreSQL server je na 192.168.0.69" |   
| exception | "Blagić Loren PDF ima footer koji se hvata kao naziv robe" |   
| preference | "Korisnik preferira srpski latinica u svim outputima" |   
| workflow | "Proces uvoza fakture: PDF → parser → draft → naimenovanja" |   
   
![](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAnEAAAACCAYAAAA3pIp+AAAABmJLR0QA/wD/AP+gvaeTAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAANklEQVR4nO3OMQ2AABAAsSNBACPiUML0NpGACyywEZJWQZeZ2aszAAD+4l6rrTq+ngAA8Nr1AL/SBEZwuCSwAAAAAElFTkSuQmCC)  
**Životni ciklus jednog zapisa**  
proposed → verified → approved → (expired ili rejected)  
   
- **proposed** — agent je upisao, još nije potvrđeno  
- **verified** — korisnik ili drugi agent potvrdio  
- **approved** — zvanično, vraća se u pretragama  
- **expired** — zastarjelo (automatski ili ručno)  
- **rejected** — netačno, ignoriše se  
Trenutno su svi migrirani zapisi approved — direktno prihvaćeni.  
![](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAnEAAAACCAYAAAA3pIp+AAAABmJLR0QA/wD/AP+gvaeTAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAANklEQVR4nO3OMQ2AABAAsSNBCkJfFEIwwIgHRiywEZJWQZeZ2ao9AAD+4lyruzq+ngAA8Nr1AOHsBegrsOrIAAAAAElFTkSuQmCC)  
**Kako je konfigurisano za svaki agent**  
Svaki agent čita MCP konfiguraciju iz svog settings fajla i pokreće server kao subprocess:  
| | |  
|-|-|  
| **Agent** | **Konfig fajl** |   
| Claude Code | ~/.claude/settings.json |   
| Qwen Code | .qwen/settings.json (projektni) |   
| Cursor | ~/.cursor/mcp.json |   
| Codex | ~/.codex/config.toml |   
| VS Code/Cline | ~/.config/Code/User/mcp_servers.json |   
| Kiro | ~/.config/Kiro/User/mcp_servers.json |   
| Pi | ~/.pi/agent/settings.json |   
| Crush | instrukcije u ~/.crush/SYSTEM.md |   
   
Svaki ima ovakav unos (format varira po agentu, ovo je JSON verzija):  
"project-memory": {  
   "command": "/usr/bin/python3",  
   "args": ["/home/radovan/.mcp_memory_system/run_server.py"],  
   "env": { "PYTHONPATH": "/home/radovan/.mcp_memory_system" }  
 }  
   
![](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAnEAAAACCAYAAAA3pIp+AAAABmJLR0QA/wD/AP+gvaeTAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAANUlEQVR4nO3OMQ2AABAAsSNhwgJGkPcrHpnRgQU2QtIq6DIze3UGAMBf3Gu1VcfXEwAAXrseaJkELjbMzy0AAAAASUVORK5CYII=)  
**Šta se dešava kad agent otvori projekt**  
1. Agent učita MCP konfiguraciju  
2. Pokrene python3 run_server.py kao pozadinski proces  
3. Komunikacija ide kroz stdin/stdout (JSON-RPC protokol)  
4. Agent može pozivati alate kao da su ugrađeni  
5. Server čita/piše u lokalnu PostgreSQL bazu mcp_memory  
![](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAnEAAAACCAYAAAA3pIp+AAAABmJLR0QA/wD/AP+gvaeTAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAANklEQVR4nO3OQQmAABRAsScYxpg/h5VMYARvRrCCNxG2BFtmZquOAAD4i3Ot7mr/egIAwGvXA224BcUMk6pDAAAAAElFTkSuQmCC)  
**Kako pogledati šta je u bazi**  
# Sve memorije za deklarant_pro  
 psql -U radovan -d mcp_memory -c \  
   "SELECT memory_type, summary FROM memory_records WHERE project_id='deklarant_pro' ORDER BY created_at DESC LIMIT 20;"  
   
 # Statistika  
 psql -U radovan -d mcp_memory -c \  
   "SELECT memory_type, count(*) FROM memory_records WHERE project_id='deklarant_pro' GROUP BY memory_type;"  
   
 # Svi projekti  
 psql -U radovan -d mcp_memory -c "SELECT project_id, name FROM projects;"  
   
![](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAnEAAAACCAYAAAA3pIp+AAAABmJLR0QA/wD/AP+gvaeTAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAANUlEQVR4nO3OMQ2AABAAsSNBCUpfEJ5YGBDBgAU2QtIq6DIzW7UHAMBfHGt1V+fXEwAAXrseHDYF+yOk59sAAAAASUVORK5CYII=)  
**Ručno testiranje servera**  
# Provjeri radi li server  
 echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' \  
   | python3 ~/.mcp_memory_system/run_server.py 2>/dev/null  
   
 # Dohvati kontekst projekta  
 echo '{"jsonrpc":"2.0","id":1,"method":"initialize",...}  
 {"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"get_project_context","arguments":{"project_id":"deklarant_pro"}}}' \  
   | python3 ~/.mcp_memory_system/run_server.py 2>/dev/null  
   
![](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAnEAAAACCAYAAAA3pIp+AAAABmJLR0QA/wD/AP+gvaeTAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAANElEQVR4nO3OQQmAUBBAwSd8bOHVnBvBkAaxgjcRZhLMNjNHdQUAwF/cq9qr8+sJAACvrQctgQNH4A++9QAAAABJRU5ErkJggg==)  
**Flat .md fajlovi — ostaju ili ne?**  
Ostaju kao backup. Flat fajlovi u:  
~/.claude/projects/-home-radovan-Desktop-deklarant-pro/memory/  
   
...i dalje postoje i Claude Code ih čita direktno (bez MCP servera). Sadržaj je i migriran u PostgreSQL, dakle postoji na oba mjesta — to je redundancija, ne problem.  
![](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAnEAAAACCAYAAAA3pIp+AAAABmJLR0QA/wD/AP+gvaeTAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAANUlEQVR4nO3OMQ2AABAAsSNhZscZXlheJwqQgQU2QtIq6DIze3UGAMBf3Gu1VcfXEwAAXrseop8EQrmJduIAAAAASUVORK5CYII=)  
   
**Poznati limiti**  
| | |  
|-|-|  
| **Limit** | **Opis** |   
| Semantic search | Nije aktivan — nema pgvector. Pretraga radi po tekstu/filterima, što je dovoljno. |   
| Pi agent | mcpServers polje dodato u settings.json, ali Pi možda to ne podržava — tek treba testirati |   
| Crush agent | Nema config fajl za MCP, samo tekstualne instrukcije u SYSTEM.md |   
| Server restart | Kad se IDE restartuje, server se ponovo pokreće — to je normalno |   
   
