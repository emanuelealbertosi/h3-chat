# Riferimenti grafici e Studio — ambito e stato

Aggiornamento del 28 ottobre: la parte Studio/flashcard è implementata nella
source, con progetto e RAG esistenti, citazioni consultabili, ripasso,
spiegazioni ed esportazione. La guida operativa è in [studio.md](studio.md).
L'attivazione locale è registrata separatamente in
`work/study-2026-10-28/studio-activation.json`; senza quel riscontro non va
confusa l'implementazione con il server già aggiornato. La sezione seguente
resta la proposta per la riproduzione di locandine e brochure.

Richiesta del 28 ottobre 2026: prima completare Locandine e le tre prove manuali,
poi valutare «fammela uguale / miglioramela» da locandina o brochure e chiarire
la proposta di flashcard del collega. Questo documento non avvia nuovi job.

## Locandina o brochure come riferimento

Il percorso pratico è: allegato → estrazione/OCR e Vision → piano spaziale
verificabile → composizione grafica/testi → anteprima modificabile.

Per PDF digitali conviene estrarre direttamente testo, coordinate e immagini:
è più fedele che ridisegnare tutto da una fotografia. Per PDF scansionati e
immagini occorrono OCR e Vision, con dimensioni effettive del riferimento,
identificazione delle aree e controllo del testo riconosciuto. La descrizione
Vision deve distinguere osservazioni, stime e dati non leggibili.

Due comportamenti distinti:

- **Riproduci il layout:** conserva proporzioni, ordine, allineamenti e materiali
  originali quando disponibili; non applicare automaticamente un nuovo margine
  che sposti l'intero impaginato. Font mancanti e testo ambiguo vanno segnalati.
- **Migliora il layout:** conserva informazioni e identità grafica richieste,
  rivedendo gerarchie, spazio, contrasto e composizione. MOSS può creare nuove
  parti visive e brevi scritte; HTML mantiene i contenuti precisi modificabili.

Le brochure richiedono un modello multipagina con fronte/retro o pieghe, non una
serie di poster indipendenti. «Uguale» non promette identità dei pixel da un
generatore: per fedeltà esatta si preservano gli elementi originali. Il riuso
del piano condiviso e dei controlli tipografici delle Locandine è possibile.

La richiesta successiva riguarda anche una foto da cambiare di stile prima di
creare il poster. L'Agente è adatto a concatenare modifica immagine (per esempio
Qwen Edit), selezione del risultato come risorsa e `create_posters`. I tool e i
collegamenti fra artefatti esistono. Il percorso è ora attivo localmente, con
`edit_image.image_id` collegato a `create_posters.hero_asset_id` e composizione
HTML. La prova completa simulata conserva il solo file ritoccato e avvia una
sola generazione; non è ancora una prova di inferenza reale. Il ritocco non
promette identità fotografica esatta da img2img. L'Assistant nel singolo tool
basta per la pianificazione, non sostituisce
l'orchestrazione esplicita di una sequenza di operazioni.

Le scritte raster MOSS possono avere lettering pittorico, neon, rilievo o altri
effetti coerenti con la grafica: le prove jazz/astronomia/botanica mostrano già
lettering diversi. Il piano HTML ora dispone anche di sei famiglie locali,
profili tipografici ed effetti decorativi selezionabili nella modale, da prompt
e dall'Agente. Sei stili sono stati verificati nell'anteprima e nei PNG, con
controllo del PDF e dei font incorporati. I contenuti lunghi restano leggibili.

## Studio e flashcard: integrazione realizzata

La richiesta del collega è stata adattata a H3: il pulsante Studio offre
flashcard, sintesi/briefing, FAQ, guida, cronologia e dialogo. Il canvas contiene
fronte/retro, Spiega, citazioni consultabili, modifica, ripasso persistente,
completamento delle schede mancanti e CSV/JSON. Le importazioni di pagine,
sottotitoli YouTube e tracce audio/video alimentano il RAG del progetto per
tutti gli strumenti, non un archivio separato.

Vedi [studio.md](studio.md) per uso e limiti verificati. Pacchetti Anki APKG,
ripasso a intervalli programmati, sessioni HTML offline e sincronizzazione tra
dispositivi restano estensioni future. Con un provider API, gli estratti
necessari vengono inviati al provider: RAG locale non implica inferenza locale.

## Riproduzione di un riferimento grafico ancora da completare

Per i riferimenti grafici: un'opzione Riproduci / Migliora deve selezionare un
singolo riferimento visivo distinto dalla foto protagonista. Vision restituisce
una descrizione strutturata di box, colori, testi leggibili e incertezze; il
piano viene conservato con l'artefatto. Per PDF digitali si estraggono coordinate
e risorse originali prima della Vision. La brochure resta multipagina con
ordine delle facciate esplicito. Questi percorsi non sono ancora attivati.
