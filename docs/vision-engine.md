# Ming Image 0.1 Design e Qwen Image 2.1

H3-Chat esegue questi modelli con un worker privato e una copia isolata della
libreria di inferenza ComfyUI. Non avvia un server ComfyUI, non legge custom node
o workflow dell'utente e non richiede ComfyUI, LM Studio o Python installati.
Il worker comunica esclusivamente tramite pipe con H3-Chat. Non espone porte.
L'inferenza e i tokenizer funzionano offline dopo l'installazione.

Il pacchetto principale include Python e i motori C++. Il componente aggiuntivo
Ming / Qwen 2.1 si installa una volta dal Setup, con verifica SHA-256, dentro
`runtime/vision`. Comprende PyTorch CUDA e può occupare circa 4 GB una volta
estratto. NVIDIA CUDA e CPU sono supportati; Vulkan non è supportato da questo
worker. Gli altri modelli mantengono i precedenti motori CPU/CUDA/Vulkan.

## Uso

Nel Setup, le sezioni Ming e Qwen Image 2.1 permettono di collegare il diffusore,
l'encoder e il VAE con **Sfoglia e collega**. I file restano nei percorsi originali,
anche su unità diverse. Questa versione del worker accetta componenti safetensors,
incluse le quantizzazioni INT8 convrot / W4A8 dei workflow di riferimento; non GGUF.
Per Qwen 2.1 serve il suo nuovo VAE a 64 canali, non quello del precedente Qwen Image.

Preset Ming: 1024×1024, 12 step, CFG 1, Euler / Simple.
Preset Qwen 2.1: 1024×1024, 25 step, CFG 1, Euler / Simple.
I parametri si modificano per modello nelle Preferenze, attivando Avanzate.
L'editing è nativo con riferimenti (denoise 1); conserva il rapporto del primo
riferimento e adatta la risoluzione all'area impostata. Massimo quattro riferimenti.
Sampler e scheduler disponibili sono quelli del motore scelto.

In chat il menu Immagini sceglie Automatico oppure un modello specifico.
Una selezione esplicita richiede una generazione: torna ad Automatico per parlare
normalmente. Il modello Ming selezionato per i grafici viene usato per richieste
di creazione di grafici, grafi, schemi e diagrammi. Le spiegazioni restano chat;
le richieste esplicite Chart / Mermaid / SVG o di codice restano strutturate.

**Assistant On / Off** controlla la preparazione delle istruzioni. Usa lo stesso
LLM della chat e il medesimo processo se già caricato, senza un secondo LLM.
Off passa direttamente il prompt. La scelta e il modello immagini vengono salvati
con ogni messaggio e non cambiano retroattivamente i lavori in coda.

**Vision On / Off** è attivo di default. On carica l'eventuale mmproj sulla CPU,
anche in modalità Residenti, lasciando VRAM all'LLM. Off non carica il proiettore.
Si applica alla chat e alla lettura dei riferimenti da parte di Assistant; il modello
immagini riceve comunque i riferimenti necessari all'editing. Un LLM senza vision
non riceve le immagini e non deve inventarne il contenuto. I token immagine
continuano a occupare contesto LLM; CPU vision può essere più lenta.

Con A richiesta il processo LLM termina prima di caricare il modello immagini;
creazione e modifica con gli stessi pesi riutilizzano il processo. Il worker usa
l'offload dinamico della libreria. Residenti mantiene più processi e richiede più
memoria; il proiettore dell'LLM resta comunque sulla CPU. Le stime di memoria sono
indicative. Non è garantita l'assenza di OOM per ogni modello/risoluzione/hardware.

Assistant migliora le istruzioni, ma non garantisce precisione numerica, topologica
o dei testi nelle immagini generate. Per grafici esatti da dati, usare il renderer
strutturato già incluso. Le immagini e i documenti destinati al canvas non vengono
duplicati nel corpo della risposta. Il prompt effettivo è consultabile in Avanzate.

## Sorgenti, licenze e ricostruzione

Core ufficiale: ComfyUI commit `3b4c0b0e457cf0a51cf3038e0a6750d8f96ce251`, che include
il supporto Ming e Qwen 2.1. Archivio originale:
https://codeload.github.com/Comfy-Org/ComfyUI/zip/3b4c0b0e457cf0a51cf3038e0a6750d8f96ce251
SHA-256: `4c137bc8976866bed10f9fcb7e8ad0e489c40a1acf76fca2f7140bd0a106cde8`.

Le DLL Microsoft Visual C++ sono incluse separatamente come file redistribuibili, con licenza Microsoft; non richiedono Visual Studio installato.

Il runtime distribuisce il sorgente completo del core senza modifiche, la sua
licenza GPL-3.0 e le licenze incluse nelle distribuzioni Python. Il worker
`native/vision-worker.py` è GPL-3.0-or-later e ne include l'attribuzione.
Gli altri componenti dell'app conservano le proprie licenze.

Per ricostruire il runtime, preparare un ambiente Python 3.13 Windows x64 isolato,
installare le versioni esatte di `scripts/vision-requirements.txt` (le wheel PyTorch
CUDA 13.0 provengono da https://download.pytorch.org/whl/cu130), poi eseguire
`scripts/build-vision-runtime.py` con il Python di quell'ambiente. Il builder
controlla gli hash RECORD e copia solo file delle distribuzioni: esclude script,
file .pth, cache, configurazioni private e pesi. Estrarre il core verificato in
`runtime/vision/core` con `scripts/prepare-vision-core.py`, poi eseguire
`scripts/package-vision-crt.py --redist-dir <cartella x64/Microsoft.VC143.CRT>` e
`scripts/package-vision-runtime.py`. Il pacchetto conserva un manifest per file
e aggiorna il manifest di download dell'app con dimensione e SHA-256.

I pesi si ottengono separatamente, con le proprie licenze:
- https://huggingface.co/Kijai/Ming-Image-ComfyUI
- https://huggingface.co/Comfy-Org/Qwen-Image-2.1

Le varianti Viggle Turbo richiedono LoRA e scheduler specifici: i preset standard
qui descritti non sono preset Turbo e non riducono automaticamente i passi a 4/5.

Il workflow manuale `Build optional image runtime` ricostruisce il pacchetto dalle
wheel ufficiali e dal core verificato, quindi lo carica nella bozza della release.
Il suo `vision-runtime-manifest.json` deve essere recepito in `runtimes.json` prima
di costruire il pacchetto principale e pubblicare la versione.
