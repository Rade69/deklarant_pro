# MCP Preference Tool

Alat `suggest_preference` predlaže šifru povlastice na osnovu zemlje porijekla i,
ako je dostupno, historije izvoznika.

Ako nema historijskih podataka, alat vraća praznu povlasticu i `confidence=0`.
Carinska pravila i CBBH kursevi se ne hardkoduju u ovom alatu.

Greške baze se loguju serverski, a prema klijentu se vraća generička poruka bez
SQL detalja.
