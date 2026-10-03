# Verifica 0.15.1

Importazione dei documenti RAG con la finestra file del sistema, selezione
multipla, cartella e trascinamento. I percorsi originali restano collegabili
nelle opzioni dedicate; le copie importate restano private nella cartella dati.

- Sei nuovi test Python: importazione e ricerca reale, deduplicazione senza
  riscrivere i file, nomi relativi delle cartelle, isolamento per progetto,
  rifiuto di percorsi non validi e documenti falsi/vuoti/oltre il limite,
  lavori in corso, Word reale, token HTTP e copie non esposte come pagine web.
- Browser Edge: selettore nativo con più file, importazione/indice, trascinamento,
  duplicati, errore PDF leggibile nella modale, etichette delle copie e mobile;
  nessun errore JavaScript.
- Suite completa: 255 test Python; i due test JavaScript dei grafici e i
  collaudi precedenti di canvas e slide vengono mantenuti.

Limiti invariati: 25 MB per documento e 500 documenti per progetto. I documenti
scelti nel browser vengono importati sul computer dove gira H3-Chat; il browser
non espone il loro percorso originale. Le cartelle importate sono uno snapshot,
mentre le cartelle collegate vengono controllate per nuove versioni.
