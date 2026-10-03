# Verifica 0.15.3

Correzione della composizione progressiva delle slide e dell'errore «ID o
gruppo slide non valido».

- Gli identificatori scelti dal modello vengono convertiti in identificatori
  interni; i gruppi possono arrivare dopo i figli. Un contenitore esplicito
  root conserva il suo layout. Cicli, duplicati e gruppi mancanti restano
  errori nella pagina finale.
- L'anteprima decodifica i campi al livello corretto, in qualsiasi ordine:
  il testo può comparire prima di ID, tipo e parent. I figli di un gruppo
  non ancora ricevuto restano temporaneamente visibili a livello principale.
- Una pagina non valida viene corretta dal medesimo LLM con un solo tentativo
  aggiuntivo. L'anteprima viene conservata se la correzione fallisce;
  interruzione e limite token non avviano tentativi aggiuntivi.
- Cinque nuovi test Python verificano alberi non canonici, gruppi successivi,
  ordine dei campi e stringhe con chiavi apparenti, ogni prefisso di una
  risposta progressiva, recupero automatico e limite dei tentativi.
- Il test browser verifica l'anteprima con testo ancora incompleto e gruppi
  non ancora arrivati, oltre a navigazione, formule, Mermaid, figure, fonti
  RAG, esportazione HTML/PDF e mobile. I dati dei collaudi sono sintetici.

La visibilità comincia quando il modello emette il testo. Durante analisi
Vision e scaletta viene mostrata la fase del lavoro; il ragionamento del
modello non viene trasformato in contenuto delle slide.
