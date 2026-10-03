# Verifica 0.16.0

Slide con temi, tipografia, stili, testi completi, continuazioni automatiche,
editor grafico e PowerPoint modificabile.

- 263 test Python passati, inclusi opzioni dal prompt, priorità sui controlli,
  testi completi in stile fumettoso, trasmissione delle istruzioni all'LLM,
  conservazione delle opzioni nelle revisioni e validazione delle modifiche.
- Cinque test JavaScript passati: grafici quantitativi, coordinate scatter
  distinte e duplicate, valori zero, rifiuto di metadati e stili non validi.
- Browser Edge: composizione progressiva, navigazione, LaTeX, Mermaid, immagini,
  citazioni RAG, HTML offline e PDF; temi, caratteri, tre stili, layout a colonne,
  continuazioni di prosa/codice/elenchi senza perdita dei marcatori, modifica
  del testo, trascinamento, ridimensionamento, duplicazione/eliminazione,
  annullamento/ripetizione, persistenza dopo reload e viewport mobile.
- Prima di salvare una modifica grafica viene verificata l'impaginazione;
  i dati dichiarativi non possono introdurre codice eseguibile o CSS arbitrario.
- PowerPoint reale: apertura senza riparazione della presentazione sintetica,
  16 pagine, 196 forme con testo e due grafici nativi. Export PNG/PDF da
  PowerPoint e controllo visivo; validazione di schema, relazioni e grafici
  passata. Bar e scatter mantengono i dati, inclusi zero e X distinti.
- Audit delle dipendenze: nessuna vulnerabilità segnalata.

Le prove usano esclusivamente dati sintetici, senza inferenza dei modelli
personali. La qualità delle spiegazioni rimane dipendente dall'LLM e dai limiti
di contesto/risposta. Il renderer distribuisce contenuti densi su continuazioni;
il conteggio delle pagine fisiche può superare quello dei capitoli richiesti.
Formule e diagrammi sono oggetti grafici nel PPTX, testi/riquadri/grafici dati
sono elementi nativi. La resa dei font PowerPoint dipende dai font disponibili.
