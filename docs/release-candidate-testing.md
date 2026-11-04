# Collaudare H3-Chat 1.0.0-rc.1

Questa checklist distingue i collaudi da eseguire dalle capacità già implementate.
Una casella qui sotto non indica da sola che la prova sia stata eseguita.
La versione stabile rimane disponibile separatamente.

## Installazione e piattaforme

- [ ] Windows: estrarre il pacchetto in una cartella scrivibile, anche con spazi,
  avviare e verificare che la versione visualizzata sia `1.0.0-rc.1`.
- [ ] Windows senza GPU: configurare un LLM API, chat e RAG CPU, senza avviare
  download o caricamenti di pesi generativi non scelti.
- [ ] Windows NVIDIA: usare un modello già installato; verificare selezione,
  parametri effettivi, salvataggio e liberazione della memoria secondo il preset.
- [ ] Mac Apple Silicon: avviare il pacchetto nativo, provare chat/API, documenti,
  RAG ed esportazione PDF. Non selezionare componenti CUDA Windows.
- [ ] Linux Ubuntu/Kali: avvio CPU/API, documenti/PDF, permessi delle cartelle e
  componenti nativi. La compilazione CUDA non equivale a una prova su GPU reale.

## Aggiornare da 0.19.2

1. Terminare i lavori e fermare il servizio. Conservare il pacchetto 0.19.2.
2. Copiare `data` a servizio fermo in una cartella di backup distinta; conservare
   `models`, i runtime già installati e le cartelle esterne dei modelli.
3. Estrarre la candidata in una cartella separata e copiarvi una copia dei dati
   da collaudare. Le chiavi protette possono dipendere da account e sistema;
   passando a un altro PC o sistema operativo può essere necessario reinserirle.
4. Avviare una sola istanza sulla cartella candidata. Verificare chat, progetti,
   fonti, raccolte, preset e collegamenti prima di fare nuove generazioni.
5. Per tornare indietro, fermare la candidata e avviare la vecchia versione con
   il backup originale. Conservare separatamente eventuali nuovi lavori della RC.

La procedura non autorizza l'eliminazione della vecchia cartella o dei suoi dati.
Chi aggiorna un checkout Git deve attendere la fine dei lavori, fermare H3,
aggiornare il codice e rieseguire l'installazione come descritto nel README.

## Percorsi funzionali

- [ ] Chat/Assistant con LLM locale e API: invio, streaming, interruzione,
  ricarica della richiesta e ripristino dei parametri.
- [ ] RAG: progetto, importazione, selezione/deselezione delle fonti, numero di
  estratti, citazioni e assenza di fonti escluse nella richiesta effettiva.
- [ ] Studio: generazione da fonti, schede e spiegazioni, ripasso ed export del lotto.
- [ ] Slide/locandine: generazione, modifica della pagina scelta, immagini già
  create, completamento delle mancanti, export HTML/PDF/PPTX e prova in Office.
- [ ] Infografiche: Normale, Decorativa, Piano sequenza, pannelli multipli,
  immagini, voci e musica, anteprima e riesportazione.
- [ ] Immagini: modello, seed, formato/MP, lotti, riferimenti, edit, zoom e confronto.
  Per Qwen 2.1 provare fino a sei riferimenti; MOSS img2img resta a uno.
- [ ] Video: T2V/I2V/riferimenti, sequenze, versioni nella timeline, stop e ripresa
  delle parti mancanti; salvataggio delle ricette e montaggio.
- [ ] Voice/Music/Trascrivi: motore scelto, durata effettiva, download e riuso.
- [ ] Agent: strumenti dichiarati, budget, conferme, stop propagato, nessun
  secondo invio in caso di risposta persa. Il controllo PC resta sperimentale.

## Segnalare un problema

Indicare versione, sistema, modalità, modello/provider, numero della pagina o
clip, messaggio d'errore e risultato atteso. Allegare il log pertinente senza
chiavi API o documenti privati. Distinguere un errore dell'app da un limite del
modello o da una differenza grafica già presente nel contenuto sorgente.
