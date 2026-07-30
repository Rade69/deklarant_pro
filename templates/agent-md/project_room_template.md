<!--
TEMPLATE. Koristiti SAMO kad impact-analiza vrati HIGH/CRITICAL (vidi
CLAUDE.md "Plan prije izmjene"). Kopirati kao
project_rooms/YYYY-MM-DD_kratak-naziv-zadatka.md, popuniti PRIJE izmjene.
Objašnjenje ZAŠTO ovaj fajl postoji: templates/agent-md/METHOD.md #5.
Fajl se na kraju može spojiti u agent_report ili obrisati — nije trajna
dokumentacija.
-->

## Cilj
<<< šta se mijenja i zašto >>>

## Pogođeno
<<< simboli/procesi iz impact-analize — broj, koji, rizik (HIGH/CRITICAL i razlog) >>>

## Plan
<<< fajlovi i redoslijed izmjena >>>

## Šta NE dirati
<!-- Scope lock — eksplicitne granice. Ovo puni "Prihvatljiv ishod" u handoff formatu. -->
<<< POPUNI >>>

## Prihvatljiv ishod (scope lock)
<<< šta MORA ostati identično nakon izmjene (npr. "validacija ostaje ista osim novog izvora dokaza") >>>

## Plan verifikacije
<!-- Vidi AGENTS.md "Definition of Done po tipu promjene". -->
<<< koji dokaz mora postojati prije nego se promjena smatra završenom >>>

## Rollback / oporavak
<<< kako se promjena vraća ili sistem oporavlja ako rezultat nije dobar (revert, backup, feature flag...) >>>

## Nezavisni checker
<!-- Vidi AGENTS.md "Nezavisna provjera". -->
<<< ko provjerava rezultat, šta provjerava, koji dokaz mora ostaviti >>>

## Konflikti
<!-- Ako postoje kontradiktorni izvori (stari agent_report, memorija, kod). Ukloniti ako nema. -->
<<< oba izvora, koji se tretira kao važeći i zašto, da li treba korisnička potvrda (DA/NE) >>>
