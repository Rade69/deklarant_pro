# ASYCUDA parity profil 2024–2026

## Datum

2026-07-28

## Agent

OpenAI Codex

## Scope

Read-only analiza `H:\New folder\NOVA ASIKUDA`, mapiranje aktivnog XML buildera
i dokumentovanje prijedloga. Runtime kod nije mijenjan.

## Status izvora

- XML arhiva 2024–2026: aktivan referentni corpus, uz nivoe pouzdanosti.
- Fajlovi prije 2024: isključeni.
- `exporters/asycuda_xml_builder.py`: aktivan runtime builder.
- `exporters/deklarant_xml_builder.py`: stara paralelna implementacija bez
  aktivnih runtime pozivalaca.
- BLAGIC-LOREN prije/poslije par: aktivan ciljani dokaz.

## GitNexus impact

Nije vršena izmjena simbola. GitNexus exploring je korišćen za mapiranje
`AsycudaXMLBuilder` pozivalaca i odgovornosti. Aktivni builder koriste
Zaglavlje controller, Agent XML workflow i XML readiness preflight.

## Šta je urađeno

- Profilisano je 1.630 XML fajlova i 4.693 naimenovanja.
- Izračunate su formule, procedure, dopunske jedinice, dokumenti, opisi i
  godišnja stabilnost.
- Trenutna implementacija je upoređena sa referentnim ishodima.
- Napravljen je P0–P5 realizacioni prijedlog.

## Zašto je urađeno

Jedan XML par može pokazati razliku, ali ne može dokazati opšte ASYCUDA
pravilo. Veliki corpus je korišćen da se odvoje univerzalne formule od
deklaracijski zavisnih obrazaca.

## Kako je urađeno

XML fajlovi su parsirani read-only. Interni datum ima prednost; inače je
korišćen datum izmjene. Rezultati su agregirani bez čuvanja identifikacionih
podataka. Pravila su provjerena i na obračunatom podskupu.

## Šta nije dirano

- Runtime kod, baze i konfiguracija.
- XML fajlovi na H: disku.
- Fajlovi prije 2024.
- Postojeće korisničke UI izmjene i nevezani Faktura plan.

## Verifikacija

- 1.630/1.630 XML fajlova uspješno parsirano.
- CIF formula: 1.629/1.629 poklapanja.
- Neto formula troškova: 1.626/1.629 poklapanja; tri anomalije dokumentovane.
- Dopunske jedinice: 462/465 tarifa imaju najmanje 95% stabilan ishod.
- Broj obrazaca potvrđen kroz raspodjelu od 1 do 66 naimenovanja.

## Pronađeni problemi

- Pogrešna formula broja obrazaca.
- Pogrešan znak odbitka i nepotpun CIF.
- Moguća dvostruka konverzija strane vozarine.
- 124/465 promašaja trenutnog dominantnog mapiranja dopunske jedinice.
- Hardkodovan način plaćanja.
- Dokumenti nisu bezbjedni za automatsko učenje samo po tarifi.
- Paralelni stari builder je drift rizik.

## Konflikti / kontradiktorni izvori

Arhiva sadrži obračunate i neobračunate XML-ove. Službena tarifa tekuće godine
ima prednost; obračunati 2026 XML je jači dokaz od starog ili praznog nacrta.
Korisnička potvrda nije potrebna za izvještaj.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `61666fb` | `docs(asycuda): dodaj parity profil 2024-2026` |

## Rizici / ograničenja

Profil je dominantno `IM/H/4000/000` i CI Bijeljina. Posebni postupci i izvoz
nemaju dovoljno veliki uzorak za punu automatizaciju.

## Potreban follow-up

Realizovati P0 kao zaseban high-risk zadatak sa parity fixture testovima, zatim
P1 dopunske jedinice.

## Potrebna korisnička potvrda

Potvrditi redoslijed realizacije: preporuka je P0 obračun/formati, zatim P1
dopunske jedinice.
