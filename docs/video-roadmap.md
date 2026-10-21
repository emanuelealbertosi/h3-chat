# Attività video successive

## Priorità concordate il 15 ottobre 2026

1. Concludere e valutare il test Character Swap a 0,98 MP per 10 secondi sullo spezzone isolato, con la nuova configurazione VEDA.
2. Character Swap a 0,98 MP per **15 secondi**: avviato come confronto prioritario, poi **annullato su richiesta esplicita dell'utente**. Job `f9b8a227f2ef47ae97af43d0da443c5b`. Non riprenderlo: se ne riparlerà in seguito.
3. **Prova attuale: Aunt Cass + Character Swap, primi 10 secondi di Clip 4 a 0,98 MP.** Richiesta esplicita dopo che l'utente ha giudicato inefficace il risultato con solo Cass. Cartella `work/aunt-cass-plus-swap-098-10-2026-10-15`, chat `2c1c14fdf7e54e86a25893292a54946f`, job_id in state.json; gestore e monitor già attivi, non duplicarli. Sorgente originale `71e8b0b159204bd6888b4724ce65fcb5`, intervallo 0–10s, guida aligned e audio/labiale originali. Ref2VA INT8, LoRA Aunt Cass BH6 + Character Swap entrambi peso 1, PDD Off, 12 passi, VEDA, seed 1215790999, Assistant Off. Unica immagine di identità, necessaria a Swap e dichiarata all'utente: `3f7e9e4c04a84a12a57627ed08fce102`, fotogramma 6s dal precedente video generato Aunt Cass nel caffè. Il prompt conserva vestiti e ambiente del video guida. Il precedente Cass solo10s `4dd3a0e4fbb44d69b0f506b3a7b577f7` è completo e visto dall'utente: 19m11s totali, 71,7s per passo medio, GPU totale campionata 12,8GiB, RAM sistema 34,3GiB. Non ripresentarlo. I vecchi15s annullati e la prova solo testo restano terminali, non riprenderli.
Esito del confronto Aunt Cass + Swap10s `729fcd1d3e1e4808a9aa03673a9bd753`: completo e presentato,20m01s,75,8s per passo,GPU totale13,1GiB,RAM sistema35,3GiB; entrambi LoRA208/208,VEDA56,activation_memory attiva. Al fotogramma5s il risultato riprende caffè e camicia verde del riferimento, anziché stanza e vestiti originali: la conservazione richiesta non è soddisfatta in quel fotogramma. Movimento completo non ancora valutato. Nessuna nuova generazione avviata, monitor disattivato.

4. **Prova successiva condizionata, richiesta dall'utente:** se la prova pulita Aunt Cass a 0,98 MP va male, provare a 0,70 MP con Aunt Cass e anche Character Swap. Non accodare anticipatamente e non confondere un esito tecnico con il giudizio visivo dell'utente. Conservare questa richiesta come attività successiva al risultato attuale; la ricetta completa del confronto andrà resa esplicita prima dell'invio.
5. Soltanto dopo il resto del lavoro: integrare facoltativamente la continuità lunga e la rifinitura ispirate a LongTakeNoCuts.

## LongTakeNoCuts — implementazione sperimentale autorizzata in background

L'utente ha successivamente chiesto di implementare l'opzione in background mentre il video attuale genera. Percorso sperimentale implementato e verificato su CPU/browser: dettagli in [video-longtake.md](video-longtake.md). Disattivato di default; il collaudo GPU e Kratos non sono avviati da questa autorizzazione. Non installa segmentatori e non si applica ai lavori già accodati. L'attivazione sul server attuale deve aspettare un aggiornamento a coda libera.

Fonti da verificare e fissare a un commit quando si implementa:

- [Progetto H3-LongTakeNoCuts](https://github.com/xyzDist/H3-LongTakeNoCuts)
- [Caso di studio condiviso dall'utente](https://www.reddit.com/r/StableDiffusion/comments/1x6jui1/h3_longtakenocuts_straight_3mins_video_case_study/)

Il metodo aggiunge un passaggio di rifinitura e una fusione temporale dei latenti; il codice consente una maschera per limitare la fusione al personaggio. La segmentazione automatica, il passaggio di rifinitura e il salvataggio dei latenti sono componenti distinti da valutare. Conservare copyright e licenza MIT delle parti eventualmente riutilizzate.

### Vincoli richiesti

- Opzione inizialmente disattivata, selezionabile per richiesta/clip senza cambiare i preset o il comportamento delle richieste già salvate.
- Conservare il generatore di video musicali lunghi: regia, segmenti, traccia audio originale continua, durate e sincronizzazione, montaggio, ripresa dalle clip mancanti.
- Conservare la modifica puntuale di ogni clip e intervallo, la selezione delle versioni, l'anteprima timeline, le inserzioni/rimozioni e il montaggio delle versioni scelte.
- Una modifica locale non deve comportare una rigenerazione silenziosa dell'intero filmato. Rendere esplicite eventuali dipendenze dai latenti delle clip adiacenti e non riutilizzare contesti incompatibili o superati.
- Conservare originali, versioni precedenti e metadati di generazione. I nuovi dati devono distinguere generazione base, rifinitura, fusione, maschera e risoluzione nativa dal successivo adattamento per il montaggio.
- Il contesto temporale usato ai raccordi non deve duplicare fotogrammi o spostare l'audio nella timeline finale.
- Non introdurre obbligatoriamente SAM3 o altri modelli residenti. Valutare una prima integrazione senza segmentazione e un'eventuale maschera come opzione separata.
- Esporre il costo della rifinitura; una maschera non dimostra da sola un minor costo di memoria o di attenzione. Misurare tempi e memoria effettivi sull'hardware dell'utente.

### Verifica prima dell'attivazione

- **Primo collaudo sul campo concordato:** rigenerare da zero il video completo di Kratos a **0,70 MP**, usando le impostazioni iniziali. La prima generazione completa è `1f9b2d892e3d4d7a800bf50eccd6d781`, chat `a6171ba99af940e08ee06af179833118`: MiniMax H3 Hybrid, 12 passi, 14 clip, circa 197,5587 secondi, 16:9, Kratos.mp3. Ricetta e parametri originali sono conservati localmente in `work/kratos-longtake-baseline-070/recipe.json`; non confonderli con i successivi rifacimenti a 0,98 MP o Z-Image.
- Per Kratos rigenerare tutti gli spezzoni, conservando prompt/regia iniziali, riferimenti, audio e seed salvati. L'opzione nuova non deve trasformare gli stacchi voluti della regia in una ripresa unica. Questo collaudo è successivo all'implementazione differita, non una generazione da avviare adesso.
- Con opzione disattivata: controllare il percorso esistente di video musicale lungo, montaggio e ripresa, senza modifiche involontarie ai parametri.
- Con opzione attivata: confronto controllato della continuità su più clip, inclusi volto e sfondo; niente promesse di assenza totale di deriva o stacchi.
- Modificare una sola clip centrale, scegliere una sua versione precedente e ricomporre l'anteprima con audio originale: le clip non richieste devono essere riutilizzate.
- Verificare cancellazione, ripresa e compatibilità dei progetti precedenti, senza sovrascrivere i video esistenti.
