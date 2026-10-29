# Impostazioni video della singola richiesta

In chat scegli **Video → Impostazioni Video → Impostazioni avanzate**.

## Animare una foto: I2V con Assistant o Agente

Allega l'immagine, scegli **Video** e scrivi per esempio:
«Crea un video I2V di 5 secondi. Usa l'immagine 1 come primo fotogramma.
Mantieni l'inquadratura iniziale e anima soltanto un movimento lento della camera».
Puoi lasciare **Assistant On**: l'app conserva il ruolo di primo fotogramma
anche se il piano LLM propone soltanto una reference. Con più immagini indica
il numero preciso; il numero riguarda le immagini, separatamente dagli audio.
Le altre immagini possono restare riferimenti d'identità o fotogrammi successivi.

In **Agente**, abilita prima **Consenti generazione, modifica e montaggio video**.
Lo strumento `create_video` accetta `input_mode: "i2v"`: la prima immagine
esplicitamente selezionata diventa il fotogramma iniziale, anche passando
`assistant: true`. `auto` conserva la normale scelta dal prompt. L'Agente usa
le impostazioni video salvate e può specificare durata, formato e risoluzione.
Non serve un LoRA Character Swap per animare il fotogramma iniziale.

Nella parte principale della stessa modale scegli **Formato video** e **Durata segmenti**. Un formato esplicito (16:9, 9:16, 1:1, 4:3 o 3:4) prevale sul prompt e sulle proporzioni delle immagini, anche per i fotogrammi iniziali. **Automatico** mantiene il comportamento precedente.

**Risoluzione video** offre i pulsanti **Preset / 0,50 / 0,70 / 0,98 MP**. Il pulsante Preset mostra la risoluzione effettiva del modello; il riepilogo sotto il prompt mostra sempre i MP del prossimo video. Scegliere 0,70 o 0,98 MP attiva il profilo Alta per evitare il limite di Media a 0,50 MP. Tornare a Media rimuove la risoluzione esplicita e applica il suo limite. La risoluzione scelta resta nella chat anche cambiando modello; Ripristina preset la azzera. Non cambia i preset amministrativi né un video in corso.

**Seed video** offre **Preset / Casuale · nuova variante / Fisso**. Casuale salva `-1` nella richiesta e sceglie un nuovo seed per ogni clip a ogni lancio. Fisso accetta un intero da 0 a 2147483647. I seed effettivi restano nei dettagli della generazione. Modifica clip offre le stesse scelte; Ricrea video offre anche **Conserva originali**, che conserva i seed delle singole scene. Per una nuova variante dello stesso spezzone, riapri la stessa clip, conserva prompt e riferimenti e scegli Casuale. Una richiesta già in esecuzione conserva la configurazione con cui è stata avviata.

I pulsanti **5 s / 10 s / 15 s** impostano il limite dei segmenti. Con un audio, il planner e la continuazione rispettano quel limite mantenendo l’intera traccia e una coda finale eventualmente più breve. Il numero di clip indicato nel prompt deve bastare a coprire la durata con il limite scelto. Il valore predefinito per i video con audio resta 15 s.

- **Modello video:** il modello predefinito delle Preferenze oppure un altro modello collegato. Selezionando un modello si parte dal suo preset tecnico, conservando formato e risoluzione espliciti della chat.
- **Accelerazione attenzione:** preset del modello, Automatico/Sage, VEDA con gruppi automatici, **VEDA 8**, **VEDA 56**, SageAttention, **ComfyKitchen INT8 · sperimentale**, oppure **Nessuna accelerazione aggiuntiva · PyTorch**. Le stesse scelte sono disponibili nelle Preferenze del modello, in Modifica clip, Ricrea video e nell’inserimento di clip.
- **PDD:** preset del modello, spento o attivo. PDD imposta 8 passi, Euler, CFG 1 e shift video/audio 12/3. Usa l’adattatore compatibile già configurato oppure selezionalo nell’elenco o dal filesystem. Sugli Hybrid resta sperimentale.
- **Ripristina preset del modello:** torna al modello predefinito, qualità Alta e parametri salvati nelle Preferenze.

Le scelte si conservano nella chat e vengono fotografate nella richiesta accodata. Non modificano i preset amministrativi né una generazione già partita. **Rigenera** conserva la configurazione della richiesta; **Riutilizza** la ripropone nel prompt. Se scegli 12, 16 o 20 passi standard, PDD viene disattivato.

Il riepilogo sotto il prompt indica modello, attenzione e stato PDD. Nei video su server esterno PDD e accelerazione locale si configurano sul server.

VEDA automatico conserva la protezione memoria che può portare a 56 gruppi i video con molte righe di attenzione, compresi i riferimenti video alla risoluzione nativa. VEDA 8 e VEDA 56 salvano invece una scelta esplicita: il motore non la sostituisce con l’euristica automatica. Più gruppi riducono il lavoro simultaneo, con un possibile costo nei tempi; la scelta più veloce dipende dal caso. La modalità e i gruppi effettivi vengono salvati con il risultato.

Per una richiesta con il pulsante Video attivo puoi anche scrivere `VEDA 8` o `VEDA 56` nel prompt, oppure aggiungere una riga `Accelerazione: ComfyKitchen`, `Accelerazione: Sage` o `Accelerazione: nessuna`. Il menu della richiesta prevale sul testo. Direttive contraddittorie vengono rifiutate prima dell’accodamento. La normale conversazione non viene interpretata come una selezione dell’acceleratore.

ComfyKitchen seleziona l’implementazione INT8 dell’attenzione presente nel runtime, incluso il percorso che libera Q/K/V dopo la quantizzazione. Se il kernel o la GPU non sono compatibili, il lavoro restituisce un errore esplicito senza cambiare acceleratore. La scelta riguarda l’attenzione del diffusore: il resto del motore, i LoRA, l’audio e le ottimizzazioni dei pesi INT8 restano condivisi. PyTorch disattiva VEDA/Sage/ComfyKitchen per l’attenzione aggiuntiva, conservando CUDA e l’attenzione nativa SDPA. Non significa elaborazione su CPU.

I test di integrazione verificano le opzioni lungo la coda, la ricarica richiesta, la ricreazione di tutte le clip e la modifica locale; i test del browser verificano i menu e i preset. Non è ancora stato svolto un confronto GPU fra ComfyKitchen, Sage e PyTorch su questa ricetta. Le nuove scelte restano disabilitate quando il server in esecuzione non espone ancora questa funzionalità; diventano disponibili dopo l’aggiornamento a coda libera. Il video già avviato conserva la sua configurazione.

Il pulsante **Ricarica richiesta**, sotto una risposta anche annullata o fallita, recupera testo, allegati e impostazioni della richiesta originale. Non avvia un lavoro e non cancella la versione precedente: modifica il prompt, scegli il formato o i segmenti e premi **Invia** quando sei pronto. **Riutilizza** resta disponibile nel riquadro della richiesta.
# Preset sperimentale 10Eros Beta5 / Beta7

Er_sde e Sgm_uniform sono disponibili nelle preferenze video e nella
rigenerazione. H3 standard può scegliere VSA 90% sparsità con ComfyKitchen
INT8; il percorso è distinto da VEDA e non richiede i gate di FastH3.
FastH3 mantiene la propria ricetta e la verifica dei gate.
Il runtime usa attenzione densa sotto 12288 token: 90% è l'obiettivo della
parte sparsa, non una misura garantita per ogni chiamata.

La ricetta richiesta per entrambi i 10Eros è 8 passi, CFG 1, Er_sde,
Sgm_uniform, shift video/audio 12/3, 0,98 MP, 16:9, VSA, PDD disattivato.
Il canvas è 1344×768; l'esportazione conserva il 16:9 a 1344×756.
La Beta5 locale è Hybrid senza Turbo aggiuntivo; la Beta7 ha il Turbo incluso.
I preset sono distinti per modello e non modificano gli altri modelli.

Questa integrazione rimane a un passaggio e 24 fps. Il secondo passaggio
2K a 4 passi/denoise 0,35 e RIFE 4.9 a 48 fps del workflow condiviso
non sono eseguiti dal worker attuale e non sono dichiarati attivi.
