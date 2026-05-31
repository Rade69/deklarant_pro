"""Skripta za punjenje baze podataka iz JSON fajlova."""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.db import get_db_connection

BASE = os.path.dirname(os.path.abspath(__file__))

def load(f):
    with open(os.path.join(BASE, f), encoding='utf-8') as fp:
        return json.load(fp)

def run():
    with get_db_connection() as conn:
        cur = conn.cursor()

        # Drzave
        data = load('drzave.json')
        cur.execute("DELETE FROM catalogs.drzave")
        for r in data:
            cur.execute("INSERT INTO catalogs.drzave (sifra, naziv) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (r['sifra'], r['naziv']))
        print(f"✅ Drzave: {len(data)}")

        # Carinski postupci
        data = load('carinski_postupci.json')
        cur.execute("DELETE FROM catalogs.carinski_postupci")
        for r in data:
            cur.execute("INSERT INTO catalogs.carinski_postupci (sifra, naziv, opis) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                        (r.get('sifra'), r.get('oznaka', ''), r.get('opis', '')))
        print(f"✅ Carinski postupci: {len(data)}")

        # Pakovanja
        data = load('sifra_pakovanja.json')
        cur.execute("DELETE FROM catalogs.pakovanja")
        for r in data:
            cur.execute("INSERT INTO catalogs.pakovanja (sifra, opis) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (r['sifra'], r.get('naziv', '')))
        print(f"✅ Pakovanja: {len(data)}")

        # Vrste prijevoza
        data = load('sifre_vrste_prijevoza_polje25_26.json')
        cur.execute("DELETE FROM catalogs.vrste_prijevoza")
        for r in data:
            cur.execute("INSERT INTO catalogs.vrste_prijevoza (sifra, naziv) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (str(r.get('sifra', '')), r.get('naziv') or r.get('opis', '')))
        print(f"✅ Vrste prijevoza: {len(data)}")

        # Vrste deklaracija - složena struktura
        raw = load('sifre_vrste_carinske_deklaracije_polje1_v2.json')
        cur.execute("DELETE FROM catalogs.vrste_deklaracija")
        count = 0
        for _key, section in raw.items():
            for entry in section.get('sifre', []):
                for sub in entry.get('sifre_polja_37', []):
                    cur.execute("INSERT INTO catalogs.vrste_deklaracija (sifra, naziv) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                                (sub['sifra'], sub.get('opis', '')[:500]))
                    count += 1
        print(f"✅ Vrste deklaracija: {count}")

        # Izjave o poreklu (povlastice)
        data = load('povlastice.json')
        cur.execute("DELETE FROM catalogs.izjave_o_poreklu")
        for r in data:
            cur.execute("INSERT INTO catalogs.izjave_o_poreklu (sifra, naziv) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (r['sifra'][:10], r.get('opis', '')[:500]))
        print(f"✅ Izjave o poreklu: {len(data)}")

        # Priloženi dokumenti
        data = load('prilozbeni_dokumenti_sifre.json')
        cur.execute("DELETE FROM catalogs.prilozeni_dokumenti_sifre")
        for r in data:
            cur.execute("INSERT INTO catalogs.prilozeni_dokumenti_sifre (sifra, naziv) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (r['sifra'][:10], r.get('opis', '')[:200]))
        print(f"✅ Priloženi dokumenti: {len(data)}")

        # Prethodni dokumenti
        data = load('popis_skracenica_dokumenta_polje40.json')
        cur.execute("DELETE FROM catalogs.prethodni_dokumenti")
        for r in data:
            cur.execute("INSERT INTO catalogs.prethodni_dokumenti (sifra, skracenica, vrsta_dokumenta) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                        (r.get('skracenica', '')[:10], r.get('skracenica', '')[:10], r.get('vrsta_dokumenta', '')[:200]))
        print(f"✅ Prethodni dokumenti: {len(data)}")

        conn.commit()
        print("\n✅ Baza uspješno popunjena!")

if __name__ == '__main__':
    run()
