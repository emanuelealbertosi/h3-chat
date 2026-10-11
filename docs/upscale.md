# Upscale video

Premi **Upscale** sotto un video nella chat o nel canvas. Il pulsante **↗ Upscale** accanto alla galleria permette di scegliere anche un video esterno dal PC o dalla galleria. Il caricamento standard accetta MP4 fino a 64 MB; i video già generati e presenti in galleria non richiedono un nuovo caricamento.

Scegli un motore:

- **Rapido · RTX VSR**: NVIDIA RTX Video Super Resolution, qualità High predefinita, Ultra opzionale. Lavora su ogni fotogramma, fino a 4×.
- **Qualità · SeedVR2**: SeedVR2 3B FP8 con VAE FP16; ricostruisce i dettagli considerando anche i fotogrammi vicini. Batch 9, tile VAE 512, seed 42, correzione colore Lab, rumore aggiunto disattivato.

Entrambi sono autonomi e usano la GPU NVIDIA su Windows. Non richiedono un server ComfyUI. Non eseguono interpolazione: conservano i fotogrammi e i tempi originali, comprese frequenza variabile e rotazione di visualizzazione. L'audio AAC di un video intero è copiato senza ricodifica; altri codec e prove brevi vengono convertiti in AAC. Il file originale resta disponibile; il nuovo MP4 viene registrato in chat, canvas e galleria come gli altri video.

## Impostazioni

In **Impostazioni → Upscale video** puoi installare il runtime CUDA Python condiviso con gli altri motori, RTX VSR, il motore SeedVR2 e i suoi pesi. I download sono opzionali e verificati con dimensione e SHA-256. Il pacchetto NVIDIA proviene dal distributore ufficiale; non viene incluso nel repository GitHub.

Puoi collegare il modello **SeedVR2 3B FP8** e il suo VAE **FP16** attraverso **Sfoglia**, anche da due cartelle diverse. Non vengono copiati. Gli altri modelli SeedVR2 non sono selezionati automaticamente.

Le impostazioni predefinite comprendono motore, risoluzione, qualità RTX, dimensione dei blocchi e delle tile, seed, blocchi da spostare in RAM, conservazione del colore e compressione MP4. Nella modale di ogni richiesta, **Parametri avanzati** permette modifiche soltanto per quell'elaborazione. I percorsi dei pesi sono riservati all'amministratore; gli ospiti possono usare i motori configurati.

**2×** e **4×** moltiplicano le dimensioni originali. **1080p**, **1440p** e **4K** indicano il lato corto, conservando le proporzioni anche nei filmati verticali. Scegli un formato maggiore dell'originale; il limite è 8K sul lato lungo. Prima di elaborare un video intero puoi selezionare **Prima una prova di 10 secondi**, indicando il punto iniziale.

## Memoria e recupero

L'upscale entra nella stessa coda delle generazioni e dell'indicizzazione GPU. Ogni utente mantiene il limite di una richiesta attiva o in coda. Prima del caricamento vengono liberati i modelli di generazione. Non viene caricato alcun LLM e non viene interrogato il RAG.

Il video viene letto e salvato a blocchi, senza caricarlo interamente in RAM. SeedVR2 usa quattro fotogrammi precedenti come contesto tra i blocchi; i modelli vengono conservati in una cache RAM durante la richiesta. Blocchi e tile più piccoli, oppure lo spostamento di blocchi in RAM, riducono la memoria GPU richiesta.

Se interrompi una richiesta o si verifica un errore, **Rigenera** recupera i blocchi completati e verificati. Il file sorgente, i parametri e i pesi devono restare invariati. I blocchi incompleti non vengono pubblicati. Una rigenerazione di una richiesta completata crea invece una nuova elaborazione.

## Fonti e licenze

- [NVIDIA Python VFX](https://pypi.org/project/nvidia-vfx/) e [RTX Video SDK](https://developer.nvidia.com/rtx-video-sdk): componente proprietario scaricato dal distributore NVIDIA.
- [SeedVR2 standalone](https://github.com/numz/ComfyUI-SeedVR2_VideoUpscaler), revisione `4490bd1f482e026674543386bb2a4d176da245b9`.
- [Pesi SeedVR2](https://huggingface.co/numz/SeedVR2_comfyUI), revisione `09ced71023636e9bc8cdf9cdecfb2625d1e691e8`, Apache-2.0.

SeedVR2 è un modello di ricostruzione: i dettagli aggiunti possono differire da quelli reali. La prova breve permette di confrontarlo con RTX VSR prima di scegliere il motore per l'intero filmato.
