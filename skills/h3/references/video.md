# Video MiniMax H3 e timeline

## Batch e versioni alternative

`docs/video-batch.md`: il batch vale anche al primo invio dalla chat, da testo,
reference, I2V, modifica sorgente e musica, oltre a editor/aggiunta/Ricrea.
`variants` è 1–8; `variants_mode` è `clip` (stesso contesto precedente scelto)
o `video` (ogni ramo recupera il proprio contesto e produce un montaggio completo).
Il prompt può prevalere con «3 varianti per clip» o «3 versioni dell’intero video».
Pianificazione condivisa, GPU sequenziale, seed base + indice; dati effettivi
nelle versioni della timeline. I take completati hanno un journal atomico in
`outputs/JOB[/scene-NNN]/batch/scenes.json`; non confonderlo con il checkpoint
della timeline. La ripresa deve riutilizzare quei take, senza rigenerarli e senza
inventare risultati. Le alternative parziali vanno tutte rimontate contro la
stessa sorgente selezionata. Esegui prove reali GPU solo entro la richiesta
umana corrente, rispettando altri lavori e stop. Verifica l’attivazione
effettiva del backend (`video_options.batch_controls`) prima di dichiararlo disponibile.

## Generazione e prompt

Leggi `docs/video-engine.md`, `docs/video-request-options.md`, `docs/video-model-selection.md` e `docs/veda.md` secondo il problema. Parametri reali, quantizzazione e memoria sono in `video-plan.json`, `scenes.json` e log del job; VRAM totale e RAM di sistema includono altre applicazioni.

Scegli la modalità corretta:
- Rigenera / riferimenti: ricrea la clip da identità e direzione; non copia automaticamente i movimenti di un video non passato al motore.
- I2V: una vera immagine iniziale, con composizione vincolante all'inizio.
- Modifica video: video sorgente e intervallo allineato, con guida audio opzionale e keyframe; leggi `docs/video-source-edit.md` e `docs/video-edit-loras.md`.
- Memoria: continuità nativa tra scene, distinta dalla guida temporale di un video sorgente.

Le Picture sono numerate per tipo media, separatamente dagli Audio. Nell'editor gli indici Picture del prompt sono quelli della timeline; il server li rimappa ai soli riferimenti selezionati per la clip. Le card multivista sono UNA identità, non più personaggi. Le reference reali prevalgono sul design canonico del personaggio.

Prompt inglese, azioni in ordine, pochi cambi e cast limitato per singola inquadratura. Dialoghi/testi restano nella lingua originale. Se disponibili, applica le skill MiniMax specifiche per il formato dei prompt, senza dipenderne per le operazioni API. Nella riscrittura full-reference i sei campi sono subject_definitions, summary, retention_analysis, detailed_description, overall_soundscape, non_diegetic_music. Primo shot senza timestamp; successivi con tempi locali crescenti. Non chiedere cinque azioni incompatibili nello stesso secondo. Un seed nuovo non corregge una regia impossibile.

Assistant Off conserva il prompt e applica un piano deterministico; non equivale a una pianificazione LLM. Per uno storyboard diretto a scene esplicite esiste il blocco JSON `h3-storyboard`: schema e limiti in `h3chat/video_direct_storyboard.py` e documentazione in `docs/video-engine.md`. Non assumere che una lunga descrizione libera diventi automaticamente una scaletta corretta.

## Modificare una timeline

Prima: GET `/chats/CHAT/video-edit/SOURCE` per capacità, immagini, versioni e clip. POST `/chats/CHAT/video-edit` accoda una nuova revisione; schema in `h3chat/video_edit.py::request/validate_edits` e `ui/video-edit.js`. Il corpo comprende source, versions, patches, assistant, remount, model, parameters, video_steps, media. Non copiare ID di un altro filmato.

Una patch usa clip (1-based), prompt, images (indici globali), lip_sync, audio_guide, modalità e opzioni compatibili. Le durate/limiti provengono dalla timeline selezionata. Con remount=true si rigenerano solo le clip richieste e si riutilizzano le altre. La versione originale resta conservata. Non scrivere a mano nei checkpoint per sostituire una scena: l'installazione via motore gestisce la storia delle versioni.

`data/outputs/JOB/scenes.json`:
- `timeline`, `outputs`, `parameters`, `plan`: struttura e risultati effettivi.
- `revision_request`, `revision_completed`, `revision_generated`, `revision_plans`: revisioni e progressi.
- `clip_versions`, `selected_versions`: alternative e selezione.
- `request_context`: impostazioni e soundtrack originale, se presenti.
Leggi il codice della versione installata prima di assumere una chiave. Non tutti i checkpoint storici contengono tutti i campi.

## Recupero memoria e fotogramma finale

UI: **Modifica clip → Rigenera · riferimenti → Intera clip**. Sono due scelte indipendenti e combinabili:

- `recover_memory: true`: apertura della sequenza corrente e finali di fino a due clip precedenti, rispettando l'ultimo stacco e le versioni selezionate. La clip precedente appena rigenerata nello stesso lotto diventa la memoria effettiva. Non disponibile sulla prima clip o su un tratto parziale. Attivarla su un cut significa chiedere esplicitamente una continuazione.
- `end_frame: 'none' | 'original' | 'next' | indice_immagine`: finale libero, ultimo frame della clip selezionata, primo della successiva o immagine aggiunta. Le estrazioni sono CPU e interne alla galleria. Il frame finale è quello reale, ad esempio 359/24 a 15s24fps, non il padding del VAE.

Il finale usa UNO dei nove posti immagine. Con nove riferimenti già selezionati serve ridurli esplicitamente oppure lasciare il finale libero; non scartarne uno silenziosamente. Un finale difettoso può reintrodurre difetti. La memoria può trascinare una composizione sbagliata: esamina apertura e confini. Non applicarla ovunque per principio.

Per verificare il test controlla il keyframe finale in `revision_plans` / piano nativo e `visual_memory_recovered` nei parametri del file generato. Questo prova il passaggio dei dati; la continuità visiva si giudica guardando il risultato.

## Ripresa, montaggio e controllo

`docs/video-resume.md`, `docs/video-extension-and-library.md`, `docs/video-recreate.md`, `docs/video-timeline-preview.md`: differenza tra riprendere mancanti, rigenerare e rimontare. Stop conserva le clip installate; non confonderle con un frame intermedio non salvato. I lotti immagine hanno regole di ripresa differenti.

Per montaggi fuori produzione: rileva i percorsi delle versioni selezionate, crea una distinta ordinata in `work`, verifica codec/dimensioni e usa copia degli stream quando compatibile. Mantieni la traccia originale col segmento esatto; non mutare timeline e file sorgente. Se serve ricodifica, CPU e senza modelli GPU.

Controllo: durata esatta, 24fps se richiesto, formato e SAR/DAR, decodifica completa, presenza/livelli audio. Estrarre campioni su CPU e ispezionare anche stacchi, identità, vestiti, anatomia e comparsa di soggetti. Dire audio non silenzioso non equivale ad averlo ascoltato. I file `fitted-*` possono essere ingranditi: preferisci l'originale nativo per valutare qualità.
