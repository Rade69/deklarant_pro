# MCP Tariff History Tool

Alat `suggest_tariff_from_history` vraća prijedloge tarifnih brojeva na osnovu
historijskih deklaracijskih stavki u PostgreSQL bazi.

Alat ne donosi konačnu odluku o razvrstavanju robe. Rezultat uvijek nosi
`needs_review`, a korisnički workflow mora zadržati ljudsku provjeru.

Greške baze se loguju serverski, a prema klijentu se vraća generička poruka bez
SQL detalja.
