# Upscale video

Premi **Upscale** sotto un video nella chat o nel canvas. Il pulsante **↗ Upscale** accanto alla galleria permette di scegliere anche un video esterno dal PC o dalla galleria. Il caricamento standard accetta MP4 fino a 64 MB; i video già generati e presenti in galleria non richiedono un nuovo caricamento.

L'app usa **NVIDIA RTX Video Super Resolution**, autonomo su GPU NVIDIA e Windows, fino a 4×. La qualità High è predefinita, Ultra opzionale. Non richiede ComfyUI e non esegue interpolazione: conserva i fotogrammi e i tempi originali, comprese frequenza variabile e rotazione di visualizzazione. L'audio AAC di un video intero è copiato senza ricodifica; altri codec e prove brevi vengono convertiti in AAC. Il file originale resta disponibile; il nuovo MP4 viene registrato in chat, canvas e galleria.

## Impostazioni

In **Impostazioni → Upscale video** puoi installare il runtime CUDA Python condiviso e RTX VSR, scegliere risoluzione, qualità RTX e compressione MP4. I download sono opzionali e verificati con dimensione e SHA-256. Il pacchetto NVIDIA proviene dal distributore ufficiale; non viene incluso nel repository GitHub. Gli ospiti possono usare il motore configurato.

Nella modale di ogni richiesta, **Parametri avanzati** permette modifiche soltanto per quell'elaborazione. **2×** e **4×** moltiplicano le dimensioni originali. **1080p**, **1440p** e **4K** indicano il lato corto, conservando le proporzioni. Scegli un formato maggiore dell'originale: limite 4× e 8K sul lato lungo. Prima di elaborare un video intero puoi selezionare **Prima una prova di 10 secondi**, indicando il punto iniziale.

## Memoria e recupero

L'upscale entra nella stessa coda delle generazioni e dell'indicizzazione GPU. Ogni utente mantiene il limite di una richiesta attiva o in coda. Prima del caricamento vengono liberati i modelli di generazione. Non viene caricato alcun LLM e non viene interrogato il RAG. Il video viene letto e salvato a blocchi, senza caricarlo interamente in RAM.

Se interrompi una richiesta o si verifica un errore, **Rigenera** recupera i blocchi completati e verificati. Il file sorgente e i parametri devono restare invariati. I blocchi incompleti non vengono pubblicati. Una rigenerazione di una richiesta completata crea una nuova elaborazione.

Da 0.18.41 SeedVR2 è rimosso, compresi codice e download. Le preferenze precedenti migrano a RTX VSR; le vecchie richieste SeedVR2 non vengono convertite automaticamente: avvia una nuova richiesta RTX VSR. I video già prodotti restano disponibili.

## Fonti e licenze

[NVIDIA Python VFX](https://pypi.org/project/nvidia-vfx/) e [RTX Video SDK](https://developer.nvidia.com/rtx-video-sdk): componente proprietario scaricato dal distributore NVIDIA.
