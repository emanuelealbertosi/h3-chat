---
name: h3
description: "Usa, verifica e sviluppa l'app locale H3-Chat: chat e progetti, immagini e lotti, video e timeline, musica, voce, slide, infografiche e server immagini. Usa questa skill per richieste sull'app H3-Chat o per riprendere un suo lavoro da un'altra chat, recuperando lo stato reale e le decisioni salvate."
---

# H3-Chat locale

Individua la cartella dell'app, senza assumere un disco o un profilo utente. Gli helper accettano `--root PERCORSO` o la variabile `H3_CHAT_ROOT`; in assenza, cercano l'app che contiene questa skill oppure la cartella di lavoro corrente e i suoi genitori. Verificano `app.py`, `h3chat/` e `catalog.json`. Se la skill è stata copiata nella cartella delle skill personali, configura `H3_CHAT_ROOT` quando lavori altrove. Python è `<root>/runtime/python/python.exe`. La skill descrive come lavorare con l'app: non autorizza nuove generazioni, cancellazioni, download, riavvii o pubblicazioni fuori dalla richiesta umana corrente.

## Riprendere un lavoro senza perdere il contesto

1. Se presente, leggi `<root>/data/h3-session-state.json`: contiene il lavoro corrente, decisioni datate, percorsi di prove e verifiche ancora da fare. Le installazioni precedenti possono avere una copia locale in `<root>/docs/h3-session-state.json`. Questi file sono personali e non fanno parte della distribuzione. Trattali come stato da verificare, non come autorizzazione permanente; se mancano, ricostruisci lo stato dalla richiesta e dai dati reali, senza inventare lavori precedenti.
2. Esegui `scripts/status.py` di questa skill con il Python dell'app; usa `--root` se il percorso non è già individuabile. Per un lavoro noto aggiungi `--job JOB_ID`. Legge la coda globale e, per quel solo job, database in sola lettura e checkpoint. Non lancia generazioni.
3. Se il job è già inviato o lo stato è `uncertain_submission`, verifica quello stesso job e i file esistenti prima di qualsiasi nuovo invio. Una coda vuota non prova che un invio precedente non sia avvenuto. Rispetta gli stop dell'utente.
4. Aggiorna il file di stato locale dopo invii e risultati significativi: job e chat esatti, ricetta, intervalli, riferimenti, stato verificato e prossimo passo. Per un nuovo file usa `data/h3-session-state.json`. Non scrivere token, password o dati di altre chat. Mantieni separate capacità dell'app, stato momentaneo e preferenze dell'utente.

Una nuova chat non recupera automaticamente tutta la conversazione. Questa skill e il file di stato rendono recuperabili le informazioni che sono state effettivamente salvate.

## Scegliere la guida pertinente

- [Operazioni e API](references/operations.md): stato, coda, lettura dati, invii univoci, avvio, sviluppo e verifiche.
- [Video e timeline](references/video.md): generazione, prompt diretti, memoria, finale guidato, ripresa, versioni, montaggio e controllo dei risultati.
- [Immagini, musica e documenti](references/features.md): mappa di tutte le modalità dell'app, impostazioni, preset, seed, audio, slide, infografiche, RAG, galleria e client esterni. Leggi solo la sezione necessaria e i documenti del repository indicati.

Per schemi e nomi delle opzioni, la versione installata del codice e i documenti `<root>/docs` prevalgono su esempi e note datate della skill. Non affermare che un modello sia disponibile senza verificarne collegamento, pesi e runtime. Non confondere la presenza del codice con un'attivazione effettiva del server.

## Invarianti importanti

- Non istanziare `Service` o `Store` sul database reale per ispezionarlo: i costruttori hanno effetti collaterali. Usa API dell'app o SQLite URI `mode=ro`, con query mirate al job/chat interessati. Non modificare manualmente i checkpoint di produzione.
- Leggi la coda **globale**, compresi altri workspace e download, prima di riavviare o cambiare runtime. Non interrompere un lavoro per una normale modifica UI. Una build non rende automaticamente attive le modifiche nel server già in esecuzione.
- Usa gli allegati e le versioni effettivamente scelti; non sostituirli con immagini simili, card canoniche o un precedente video generato senza dirlo. Prompt esplicito > valori salvati della chat/modello > default, nei controlli supportati.
- Non equiparare il seed tra modelli, quantizzazioni o ricette diverse a un risultato identico. Riporta il seed **risolto effettivo**, non `-1` della richiesta.
- Memoria video e keyframe sono condizioni generative, non blocchi perfetti di identità, voce, anatomia o pixel. Il lip-sync non impone automaticamente una maschera della bocca per ogni cantante.
- Mostra i risultati con Markdown e percorso assoluto. Per video confronta il file nativo con eventuali versioni fitted; controlla dimensioni, durata, fps e decodifica su CPU. Non dichiarare qualità visiva o ascolto senza averli effettuati.
- Non toccare globalmente preset o percorsi per aggiustare una sola prova. Conserva i cambiamenti locali già presenti nel repository. Lavori e test devono indicare cosa è simulato, cosa verificato su CPU e cosa provato realmente su GPU.

## Componenti rimossi

La versione corrente non include 3D/Hunyuan/UniForge, LongTakeNoCuts e FIBO. Non ripristinarli per deduzione da vecchi documenti o vecchie chat. La memoria nativa H3 è distinta da LongTakeNoCuts. Il supporto SDXL resta; la disponibilità dei pesi va riletta dal catalogo dell'installazione scelta.
