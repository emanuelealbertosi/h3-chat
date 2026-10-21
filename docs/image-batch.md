# Lotti immagini dalla chat

In **Immagini → Impostazioni**, la sezione **Formato immagine** è in alto per tutti i modelli, inclusi Qwen, Qwen Turbo, Anima, Krea e MOSS. Scegli Automatico, 1:1, 16:9, 9:16, 4:3, 3:4, 3:2 o 2:3; la scelta resta salvata per modello nella chat. Il riepilogo delle impostazioni mostra il formato selezionato. La stessa scelta è nelle Preferenze immagini, fuori da Avanzate. Il formato scritto nel prompt prevale, anche con Assistant Off, immagini allegate e lotti; senza indicazioni il lotto conserva il formato salvato. I megapixel restano separati dalle proporzioni e la griglia del motore può arrotondare le dimensioni.

Con **Assistant On**, scrivi per esempio:

> Creami 4 immagini. La prima: un faro al tramonto, Qwen Image 2.1, immagine 1 come riferimento, 16:9, 1 MP, seed 42. La seconda: una barca sul lago, Qwen Image 2.1 Turbo, immagine 2, 16:9, 1 MP, seed 42. La terza e la quarta: un bosco e una montagna, MOSS INT8, senza allegati, 9:16, 1 MP, 30 passi, sampler euler, scheduler sgm_uniform, seed casuale per ciascuna.

Se non scrivi il modello nel prompt, ogni voce usa quello selezionato nella chat; con selezione automatica usa il modello predefinito delle Preferenze (creazione o modifica, secondo i riferimenti scelti per quella voce). Se non specifichi parametri, conserva quelli salvati per quel modello, comprese le impostazioni della modale della chat, formato, megapixel, passi, CFG, sampler, scheduler, seed e negativo. Puoi omettere solo alcuni parametri: vengono sostituiti esclusivamente quelli richiesti. Un modello esplicito diverso usa i propri valori salvati, senza ereditare i parametri della modale di un altro modello. L’assistant non può cambiare questi valori inventando impostazioni nel piano o nella descrizione.

L'assistant produce un solo piano per tutto il lotto. Ogni voce conserva modello, prompt, riferimenti numerati dall'ordine degli allegati e parametri; quelli non specificati ereditano le impostazioni del modello. Indica INT8 o BF16 se hai più versioni MOSS installate. Un seed fisso numerico viene riutilizzato dove richiesto; casuale genera seed distinti. Modelli differenti non producono immagini equivalenti soltanto perché condividono il seed.

Il piano completo viene validato prima della prima generazione: modelli disponibili, capacità create/edit, riferimenti esistenti e limiti, sampler, scheduler e dimensioni. Da 2 a 24 immagini per richiesta. Non vengono scaricati modelli mancanti. Assistant Off richiede di attivarlo per interpretare il lotto.

I nomi modello sono risolti sul catalogo installato corrente, non su un elenco fisso di varianti. Con più MOSS, il nome generico usa il MOSS selezionato come predefinito se corrisponde; altrimenti si richiede il nome più preciso. Il piano non può inventare una specificazione INT8/BF16 che non compare nel prompt. Nuovi file modello diventano utilizzabili quando hanno un collegamento pronto nel catalogo.

I controlli letterali vengono riletti anche dal prompt originale: istruzioni comuni e sezioni «la prima», «la seconda», «la terza e la quarta», oppure liste numerate. In particolare «seed fisso 99» e «seed casuale» prevalgono sui valori proposti o omessi dall'assistant. Un'introduzione con più formati diversi («due 16:9 e due 9:16») viene lasciata alla ripartizione del piano, anziché imporre l'ultimo formato a tutte le immagini.

I LoRA selezionati nel pannello conservano il destinatario assegnato. Nei lotti si possono anche allegare direttamente file `.safetensors`: vengono ispezionati come adapter, mai inviati come immagini. La famiglia viene letta da metadati o struttura; gli adapter sconosciuti vengono rifiutati. L'assegnazione automatica considera solo i modelli compatibili. Si può specificare nel prompt quale LoRA e peso usare per ciascuna immagine, anche escludendolo esplicitamente. Il file viene ricontrollato prima dell'uso; la compatibilità effettiva dei tensori viene verificata dal motore al caricamento. Famiglia comune non significa compatibilità garantita per qualsiasi futuro checkpoint.

Le generazioni procedono una alla volta. Le voci dello stesso modello vengono raggruppate per riutilizzarlo; l'ordine di presentazione resta quello richiesto. L'assistant non viene richiamato fra un'immagine e l'altra. I riferimenti sono soltanto gli allegati selezionati per quella voce: `senza allegati` non utilizza immagini della cronologia o di altre voci.

La risposta è una sola, in chat **e** nel canvas: riquadro principale, miniature numerate, zoom in modale e download dell'originale selezionato. La selezione si aggiorna fra i due riquadri. Modello, dimensioni, seed e passi effettivi sono salvati per ogni risultato; il seed compare sotto l'immagine. Il recupero dell'ultimo seed considera anche le immagini già completate nei lotti interrotti.

Ogni immagine pronta viene salvata subito nella galleria e nella stessa risposta/canvas. Stop o errore conservano i risultati precedenti. Non viene ripreso automaticamente un lotto interrotto.

Test isolati del servizio: chiamata assistant unica, modelli raggruppati, riferimenti distinti o vuoti, seed, ordine, preset invariati, conservazione dopo stop. Test browser: chat/canvas, miniature, zoom e mobile. I test del servizio usano motori simulati; la prova GPU reale è documentata separatamente in `work/image-batch-2026-10-19`.
