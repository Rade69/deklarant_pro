# MCP Validation Tool

Alat `validate_declaration_summary` provjerava osnovna centralizovana pravila za
draft deklaracije.

Prva verzija blokira više od 99 naimenovanja i, kada su stavke dostupne, provjerava
tarifne brojeve u centralnoj tabeli zvanične tarife. Alat ne zamjenjuje kompletnu
GUI validaciju.

Greške baze se loguju serverski, a prema klijentu se vraća generičko upozorenje bez
SQL detalja.
