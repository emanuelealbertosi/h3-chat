# P-H3-Image opzionale

P-H3-Image di PrunaAI è un motore immagini ed editing derivato da MiniMax H3.
Non sostituisce MOSS o Qwen. Il profilo **P-H3-Image** collega diffusore,
encoder testo/immagini, VAE e, facoltativamente, espansore prompt dedicato.

La versione compatta richiede circa 20 GB di pesi più 6,7 GB per l'espansore.
Gli autori riportano un picco di 21 GB di VRAM a 8 MP: con 16 GB è necessario
offload. I tempi su una scheda più grande non prevedono quelli del proprio PC.
Il preset iniziale è circa 4 MP; 8 MP è la risoluzione consigliata dagli autori.
La griglia è di 32 pixel e il controllo permette fino a 16 MP.

Si conserva la ricetta pubblicata: 8 passi, Euler, CFG 1 (nessuna guida CFG),
shift video/audio 1 e sigma `1, .984753, .967905, .951688, .925372, .881923,
.810083, .528718, 0`. Il negativo non viene usato. Modificare impropriamente
passi o scheduler produce un errore prima del rendering.

**Espandi il prompt con il modello dedicato P-H3** è indipendente da Assistant
e può essere disattivato nelle impostazioni del modello o della chat. Usa
decodifica greedy e thinking come nel workflow originale. Il modello accetta
fino a otto immagini: la prima è quella da modificare e le successive sono
riferimenti. Il prompt effettivo espanso è conservato nei dati di creazione.

I LoRA della famiglia MiniMax H3 sono selezionabili per P-H3 come compatibilità
sperimentale: la derivazione comune non garantisce che tutti gli adattatori
video o per personaggi funzionino bene. Il motore rifiuta un LoRA senza tensori
applicabili e registra i patch realmente applicati. Il test delle sei immagini
iniziali non usa LoRA e non costituisce una verifica della loro qualità.

Il runtime è in `runtime/ph3`, con una revisione ComfyUI separata e due
estensioni di quantizzazione. Torch e il runtime condiviso non vengono aggiornati.
I processi caldi P-H3 non vengono riutilizzati dai motori con il vecchio core.

Installazione esplicita: eseguire `scripts/install-ph3.py --models-dir PERCORSO`
con il Python dell'app. Richiede il runtime immagini base già installato.
Il manifest `scripts/ph3-sources.json` fissa revisioni e SHA-256 dei pesi.
Nessuna parte viene scaricata automaticamente quando si sceglie un modello.

Per rimuovere la prova: scollegare il modello dal Catalogo, liberare i modelli
in memoria, quindi cancellare solo la cartella dedicata dei pesi e `runtime/ph3`.
Le immagini generate restano nella galleria. Leggere la licenza distribuita con
i pesi prima dell'uso.
