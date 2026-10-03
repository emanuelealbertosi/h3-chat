# Verifica 0.15.0

Creazione di slide con la composizione dichiarativa progressiva di H3-Slides V2,
integrata nel canvas senza dipendenza dall'altra applicazione.

- Suite Python: 249 test passati, inclusi stream prima della risposta finale,
  interruzione con recupero dell'artefatto, sorgente e riferimenti non validi,
  estrazione Word reale con immagine, selezione/isolation RAG e Vision in batch
  usando un solo LLM. L'inferenza dei test usa risposte sintetiche controllate.
- Browser Edge: testo aggiornato durante la scrittura, selezione stabile delle
  pagine, formule KaTeX, Mermaid, immagini autorizzate, apertura citazioni RAG,
  recupero dopo reload e viewport mobile, nessun errore JavaScript.
- HTML offline: tutte le pagine, immagini e formule incorporate; nessuno script.
- PDF reale: tre pagine 4:3, ciascuna 960×720 punti; diagrammi e figure conservati.
- Collaudo precedente: cronologia canvas, selezione durante la generazione,
  modifiche, ripristino, export e identità dei modelli ancora funzionanti.

La qualità di contenuti e composizione dipende dal modello selezionato. I test
non misurano l'inferenza di tutti gli LLM o il contenuto dei documenti personali.
