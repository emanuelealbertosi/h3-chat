# Verifica 0.16.3

- 270 test Python e 7 JavaScript superati.
- Regressione RAG con due LLM distinti, richiesta «ricrea l’animazione» e
  artefatto precedente di 40.000 caratteri: l’estratto sul polimorfismo resta
  disponibile al generatore Manim. Le fonti restano vincolate al progetto.
- Domande nuove e argomenti espliciti non ereditano il tema precedente;
  risposte del modello e allegati non diventano termini di ricerca.
- Scheda Provider LLM collaudata nel browser desktop e mobile con dati
  sintetici: salvataggio, chiave nascosta e selezione per chat/router/Assistant.
  Nessuna chiamata a servizi esterni durante il collaudo.
- Avanzamento Manim distingue avvio LLM, scrittura della scena e rendering.
- Stato di salute espone se il lavoratore della coda è attivo.

Include le correzioni della 0.16.2 per contrasto slide, audio WAV/MP3 e durata
Manim tollerante. Nessuna accelerazione video dichiarata.
