# Verifica 0.16.13 · libri nel RAG

I progetti supportano documenti fino a 512 MiB, PDF fino a 3.000 pagine e
dieci milioni di caratteri estratti, con un massimo di 20.000 estratti per fonte.
Gli allegati diretti alla chat conservano i limiti separati precedenti.

## Controlli

- PDF sintetico valido oltre 26 MiB con 901 pagine: caricamento a blocchi,
  indicizzazione nel worker documenti e recupero del testo a pagina 901.
  Lo stesso PDF viene rifiutato correttamente dal lettore per allegati chat.
- Trasferimenti binari a blocchi da 2 MiB: deduplicazione, identità del progetto,
  ordine dei blocchi, rifiuto di documenti incompleti e oltre limite, cancellazione
  dei file temporanei su annullamento, eliminazione del progetto e chiusura.
- Endpoint HTTP autenticati: un token errato viene rifiutato; una fonte diventa
  disponibile soltanto dopo il completamento del trasferimento.
- Indicizzazione di 513 estratti con embedding simulati: ogni chiamata usa al
  massimo 32 estratti. Un errore durante il secondo gruppo conserva intatto
  l'indice precedente e rimuove il database temporaneo.
- 315 test Python eseguiti: l'unico errore iniziale era il bundle ancora da
  ricostruire. Dopo la compilazione, tutti i cinque test di installazione sono
  stati rieseguiti con successo.
- 10 test JavaScript superati, inclusi invio di un libro oltre 25 MiB tramite
  Blob, percentuale di progresso, pulizia dopo blocchi incompleti e controllo
  del limite prima dell'inizio del caricamento. UI e bundle clone ricostruiti.

La lettura PDF usa un file aperto anziché una copia completa in memoria.
I vettori dei libri vengono preparati su disco e la ricerca semantica li legge
progressivamente. La prova non misura la velocità di Ovis su un libro reale:
i tempi dipendono dall'embedding e dal dispositivo scelti. L'indice RAG non
esegue OCR; un libro scansionato senza testo richiede prima una copia con OCR.
Nessun documento personale o peso di modello viene distribuito.
