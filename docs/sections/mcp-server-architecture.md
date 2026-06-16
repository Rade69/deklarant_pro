# MCP Server Architecture

## Svrha

MCP server je backend alatni servis za Deklarant Pro. Centralizuje carinske operacije
oko PostgreSQL baze, tako da desktop aplikacija i AI agenti pozivaju dobro definisane
alate umjesto direktnog SQL-a ili lokalnih fajl-indeksa.

MCP server **nije** chat agent, **nije** UI, i **ne** razgovara sa korisnikom.
On je alatni sloj koji izlaže stabilne JSON ugovore za carinsku logiku.

## Deployment režimi

Trenutna implementacija podržava dva režima:

- **Lokalni razvojni režim:** desktop aplikacija pokreće `mcp_server.server` kao lokalni
  subprocess preko stdio JSON-RPC transporta. Ovo postoji zato što Ubuntu server sa
  PostgreSQL bazom nije uvijek dostupan tokom razvoja.
- **Ciljani produkcioni režim:** isti `mcp_server.server` modul se pokreće na Ubuntu
  serveru pored PostgreSQL baze, a desktop aplikacija/AI host poziva MCP alate bez
  direktnog nošenja produkcionih DB kredencijala u GUI procesu.

Migracija na Ubuntu ne treba mijenjati ugovore alata. Potrebno je prebaciti `.env`
na server, koristiti read-only DB korisnika, dodati systemd ili drugi nadzor procesa,
provjeriti firewall/SSH pristup i pokrenuti `python -m pytest mcp_server/tests/ -q`
u server okruženju.

## Zavisnosti i pretpostavke

- **PostgreSQL baza** na zasebnom Ubuntu serveru (192.168.0.69 ili localhost)
- **Konekcioni parametri** iz `.env` fajla (DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD)
- **Tabele**: `catalogs.declaration_items`, `catalogs.declarations`, `catalogs.zvanicna_tarifa`, `catalogs.exporter_xml_index`, `traders`
- **Python 3.10+**, paketi: `mcp`, `psycopg2-binary`, `pydantic-settings`, `python-dotenv`
- Desktop aplikacija ostaje vlasnik korisničkog workflow-a i prikaza

## Pravila i granice

| Pravilo | Posljedica kršenja |
|---------|-------------------|
| SQL je uvijek parametrizovan — nema f-string interpolacije | SQL injection ranjivost |
| Nema hardkodovanih kredencijala, IP adresa, lozinki | Sigurnosni incident |
| MCP alati ne smiju vraćati sirove SQL greške korisniku | Curenje interne strukture |
| Prva verzija je isključivo read-only — nema write alata | Nekontrolisane izmjene podataka |
| Alati vraćaju strukturisani JSON, ne HTML | Kršenje MCP protokola |
| Svaki izuzetak se hvata na granici alata i vraća kao strukturisana greška | Pad servera |
| Ne uklanjati postojeće lokalne servise dok MCP alati nisu stabilni | Regresija u produkciji |

## Zašto ovako

**Problem:** Deklarant Pro ima logiku razbacanu između SQLite indeksa (lokalno),
PostgreSQL upita (remote) i Python servisa (GUI proces). Ovo otežava održavanje,
testiranje i dodavanje novih AI agenata.

**Rješenje:** MCP server kao centralizovani alatni sloj. Svi alati pričaju kroz
stabilan stdio JSON-RPC ugovor, koriste istu bazu (PostgreSQL) i imaju stabilne
ulazno-izlazne ugovore. Lokalni adapter ostaje namjerno uzak da bi se server kasnije
mogao premjestiti na Ubuntu bez promjene tool ugovora.

**Alternative odbačene:**
- REST API — veći overhead, potrebna autentifikacija, više infrastrukture
- Direktni PostgreSQL iz GUI — bez sigurnosnog sloja, teško za testiranje
- WebSocket server — nepotrebna kompleksnost za povremene upite

**Provjera ispravnosti:** Pokrenuti `python -m pytest mcp_server/tests/ -v`. Svi
alati moraju vratiti validan JSON za sve scenarije (happy path, empty, error).
