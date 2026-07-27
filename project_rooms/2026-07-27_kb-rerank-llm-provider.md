# KB rerank kroz centralni LLMProvider

## Cilj

Ukloniti direktni Groq klijent iz `KnowledgeBaseService._groq_rerank` i
provesti poziv kroz kanonski `LLMProvider`.

## Pogođeno

GitNexus HIGH: 6 simbola, 1 direktni pozivalac i 2 procesa. Direktno je pogođen
`KnowledgeBaseService.search`, posredno root/dist `ChatWorker` KB kontekst.

## Plan

Zadržati postojeći prompt i parsiranje rezultata, zamijeniti samo provider
poziv, sinhronizovati root/dist i pokrenuti KB/LLM/logging testove.

## Šta NE dirati

BM25 indeks, ranking formule, KB sadržaj, broj kandidata, chat format i
fallback ponašanje kada LLM nije dostupan.

## Konflikti

Nema. Kanonsko pravilo projekta već zahtijeva `LLMProvider`; direktni Groq
poziv je zaostali bypass. Korisnička potvrda nije potrebna.
