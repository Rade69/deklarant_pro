# MCP Exporter Template Tool

Alat `find_exporter_xml_template` traži prethodno korišten XML template po paru
izvoznik-primalac.

Prioritet pretrage je izvoznik + JIB primaoca, zatim izvoznik + naziv primaoca,
zatim oprezni fallback samo po izvozniku. Alat vraća samo metadata i identifikator
templatea, ne kompletan XML sadržaj.

Greške baze se loguju serverski, a prema klijentu se vraća generička poruka bez
SQL detalja.
