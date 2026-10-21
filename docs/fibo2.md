# FIBO 2.0 Dev

Motore opzionale per creare e modificare immagini, con pesi BF16 originali BRIA e runtime Diffusers separato. Non usa il servizio BRIA o Gemini: la generazione è locale. Il modello richiede l'accettazione delle condizioni nel proprio account Hugging Face prima del download.

## Installazione

Gli script espliciti `scripts/install-fibo2-runtime.py` e `scripts/download-fibo2.py` preparano rispettivamente le librerie e i pesi. La generazione non effettua download automatici. Le revisioni sono bloccate in `h3chat/fibo2.py`; il downloader verifica dimensioni e SHA256 dei pesi e può riprendere i blocchi già scaricati.

Cartella comune dei modelli immagini:

`F:\sd-webui-forge-neo\models\Stable-diffusion\Fibo-2.0-dev`

In **Modelli → Collega modello**, scegliere **FIBO 2.0 Dev** e il primo shard `transformer/diffusion_pytorch_model-00001-of-00002.safetensors`. Il secondo shard deve restare accanto al primo. Encoder e VAE vengono suggeriti dalle cartelle `text_encoder` e `vae` dello stesso pacchetto; devono restare presenti anche processor, configurazioni, scheduler e font originali.

## Uso in chat e nel canvas

Selezionare FIBO nel modello immagini. Il preset iniziale segue la scheda BRIA: **50 passi, CFG 5, FlowMatch Euler, scheduler Simple, circa 1 MP**. Formato, megapixel, passi, CFG, seed e negative prompt sono modificabili dalle impostazioni immagini; i valori espliciti nel prompt hanno la precedenza. Le dimensioni esatte devono essere multipli di 16, fino a 2048 pixel per lato in questa integrazione. Per esempio: `1424x800, 50 passi, CFG 5, seed 42`.

Con **Assistant Off**, si può scrivere una descrizione o istruzione normale, oppure un JSON FIBO esplicito. Con **Assistant On**, l'assistente locale prepara la descrizione strutturata con oggetti, posizioni, materiali e stile. Un JSON usato per modificare un'immagine deve contenere `edit_instruction`.

Per le scritte, il JSON può contenere `text_render`, con una voce per frase: `{"text":"Caffè e curiosità","location":"upper centre"}`. Il motore prepara i riferimenti tipografici con i font ufficiali, conservando accenti e apostrofi. L'assistente riceve istruzioni per preparare questo campo quando chiedi testo visibile; le illustrazioni delle slide mantengono invece il divieto di scritte incorporate.

Per una modifica si possono allegare da una a quattro immagini. Per impostazione predefinita viene conservato il formato del primo riferimento; una dimensione o un formato espliciti nel prompt lo sostituiscono. I risultati di un batch appaiono nel normale gruppo immagini con miniature. I metadati conservano dimensioni effettive, seed, parametri e tempi.

## Memoria e limiti

I pesi occupano circa **25,47 GB decimali**. Su una GPU da 16 GB il worker usa offload sequenziale dei moduli fra RAM e VRAM e tiling del VAE. Questo riduce la VRAM necessaria, ma aumenta i trasferimenti e i tempi. La stima preventiva della memoria è iniziale: non costituisce un benchmark o una garanzia contro OOM. La modalità CPU usa FP32 e richiede molta più RAM.

Il controllo **Memoria GPU** nelle impostazioni del modello e della chat offre:

- **Prudente:** offload sequenziale, minima VRAM.
- **Più GPU · pesi stabili:** conserva parte del diffusore sulla GPU (massimo 10 GiB di pesi, con almeno 4 GiB di margine libero al caricamento); i blocchi rimanenti usano una copia CPU stabile. Il VAE resta sulla GPU. Numero di blocchi residenti e memoria vengono riportati nei parametri effettivi.
- **Tutto su GPU · sperimentale:** alloca l’intera pipeline su CUDA, senza offload applicativo. L’eventuale uso della RAM condivisa dipende dal driver; può rallentare o terminare con OOM. Non cambia le impostazioni NVIDIA.
- **Gruppi di 16 · sperimentale:** gruppi spostati fra RAM e VRAM. Può risultare più lento del sequenziale: occupare più VRAM non implica meno trasferimenti.

Il cambio della modalità forza un nuovo caricamento del worker. Non cambia seed, risoluzione o numero di passi.

Il runtime privato non aggiorna Torch, Transformers o gli altri motori condivisi. Il cambio di modello, il riuso nei batch e Stop seguono il normale gestore dell'app.

LoRA e maschere di modifica non sono abilitati in questa integrazione. La licenza del modello è quella della [scheda BRIA](https://huggingface.co/briaai/Fibo-2.0-dev); verificare le condizioni prima di usi commerciali.

## Variante INT8 opzionale

Il profilo **FIBO 2.0 Dev · INT8 ConvRot** usa diffusore ed encoder quantizzati
dal pacchetto Comfy-Org, con la pipeline Diffusers originale e il VAE BF16.
`scripts/download-fibo2-int8.py` verifica i pesi; `scripts/prepare-fibo2-int8.py`
prepara gli asset copiandoli da un'installazione Dev BF16 disponibile durante
l'installazione. Una volta preparata, la cartella INT8 è indipendente dai pesi BF16:
questi ultimi possono essere scollegati e cancellati senza rimuovere INT8.

I componenti passano fra CPU e GPU per fase, senza trasferire ogni blocco a ogni
passo. I controlli di memoria delle varianti BF16 non si applicano a INT8.
Prova locale 1024², 50 passi: 112,63 s totali per creazione, circa 1,78 s per
passo a regime e picco Torch di 8,61 GiB; editing della tazza in 269,41 s totali,
circa 5,18 s per passo a regime e picco 9,35 GiB. Sono misure di singoli esempi.
La quantizzazione può cambiare il risultato anche a seed uguale. Frasi brevi
leggibili non garantiscono testi lunghi corretti: la prova con testo italiano
fitto contiene numerosi errori. Le scritte delle slide restano HTML/SVG.

Qwen Image 2.1 è il modello predefinito per le illustrazioni di slide e infografiche
quando disponibile; la scelta esplicita dell'utente prevale. FIBO resta opzionale.
Il modello Edit Turbo è distinto e non è incluso in questa installazione.

Riferimenti: [modello e preset ufficiali](https://huggingface.co/briaai/Fibo-2.0-dev), [implementazione Diffusers](https://github.com/huggingface/diffusers/pull/14991).

## Prime misure locali · RTX 5070 Ti 16 GB

Prova 1024 × 1024, BF16, 50 passi, CFG 5, seed 42, stesso prompt:

| Modalità | Passo a regime | Generazione | Totale del job, caricamento incluso |
|---|---:|---:|---:|
| Prudente | circa 7,3 s | 376,92 s | 420,34 s |
| Più GPU | 4,47 s medi, escluso il primo callback | 260,77 s | 313,30 s |

Più GPU conserva 27 blocchi su CUDA e ne trasferisce 17 a richiesta. Pesi residenti 9,85 GiB; picco Torch allocato 12,53 GiB. Il primo callback include anche l’encoder e non è un singolo passo puro. L’immagine PNG delle due prove è identica byte per byte. Il confronto non dimostra la stessa velocità con immagini di riferimento o altre dimensioni. GPU totale e RAM di sistema campionate includono altre app.

La prova a gruppi di 16 è stata fermata su autorizzazione dell’utente: circa 15 s per passo, peggiore del sequenziale. La prova con allocazione completa CUDA è separata e non cambia il preset predefinito.

Nel confronto completo CUDA a 6 passi, Windows ha effettivamente impegnato circa 14,7 GiB dedicati e 10,5–10,9 GiB condivisi nel worker. Dopo oltre 6 minuti l’encoder non aveva ancora terminato e non era stato completato alcun passo di denoising. La prova è stata interrotta; non esistono un’immagine finale o un tempo per passo per questa modalità. L’utilizzo GPU riportato al 99–100% non ha coinciso con una maggiore velocità. Questa osservazione riguarda il sistema Windows/WDDM e i pesi BF16 provati, non ogni GPU o modello.
