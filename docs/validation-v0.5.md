# Verifiche H3-Chat 0.5.0

Eseguite il 13 settembre 2026 su Windows, usando il Python incluso nel pacchetto e il motore llama.cpp CPU b10809.

- 45 test Python: regressioni precedenti e nuovi test per rilevamento MTP, metadati senza pesi NextN, parti GGUF mancanti, file contenenti solo la testa, architetture sconosciute, limiti delle teste multiple, directory troncate e invalidazione della cache.
- Controlli del comando nativo `draft-mtp`, del numero anticipato e dell'interrogazione autenticata `/slots`. La mancata conferma di MTP genera un errore esplicito. Questi casi usano processi e risposte simulate.
- Regressione concorrente del catalogo: i modelli esterni restano disponibili durante la scansione e le capacità MTP sono condivise con il gestore delle sessioni.
- Validazione di valori booleani/interi, limiti del contesto, persistenza e copia delle impostazioni nei lavori già accodati. Verifica del `max_tokens` inviato nelle richieste di testo e canvas.
- Verifica delle stime aggiuntive RAM/VRAM e dell'identità della sessione: max token, Think e token anticipati con MTP spento non cambiano la sessione; attivazione MTP e variazioni effettive dei token anticipati la cambiano.
- Due test JavaScript per i grafici numerici; compilazione dell'interfaccia senza CDN.
- Prova Edge automatizzata: pannello MTP su fixture GGUF strutturale, salvataggio/rilettura, passaggio a modello incompatibile, preferenza conservata con MTP disattivato, accesso dalla chat e layout desktop/390 px. Nessun errore JavaScript.
- Due generazioni reali con Qwen3-0.6B Q4_K_M su CPU, limiti 96 e 64 token: entrambe terminano con `finish_reason: length`, conservando lo stesso processo caricato. La preferenza MTP accesa resta effettivamente disattivata su questo modello senza NextN. Questa prova verifica il limite e la gestione del processo, non la qualità della risposta del modello piccolo.

Il pacchetto estratto è stato avviato autonomamente con SmolVLM e mmproj collegati dalla cartella originale: riconosce una foto rossa, conserva max token 64 e MTP effettivamente disattivato. Nessun peso copiato nel pacchetto e hash dei file originali invariati.

Le fixture GGUF dei test contengono solo strutture minime e non sono usate per inferenza. Non è stato caricato un modello completo con pesi MTP: accelerazione, tasso di accettazione e picchi di memoria con MTP attivo non sono stati misurati su CPU, CUDA o Vulkan. Il supporto è integrato secondo il codice della versione b10809 e viene verificato dal server al caricamento; la compatibilità dei singoli modelli rimane vincolata al motore e ai loro file.

Il pacchetto portatile include Python, motori CPU, launcher e script di installazione/avvio/arresto; esclude pesi, cache e dati personali. Il manifesto `FILES-SHA256.json` contiene gli hash dei file distribuiti.
