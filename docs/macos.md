# H3-Chat per Mac con chip Apple

Distribuzione portatile per **macOS 15 o successivo, Apple Silicon arm64**. Non serve installare Python, Node, Homebrew o compilatori: il pacchetto include Python, il browser per i PDF, strumenti documenti e llama.cpp per CPU e Metal. I modelli restano separati.

1. Scarica `H3-Chat-VERSIONE-macos-arm64.zip` dalla release ed estrai tutta la cartella.
2. Sposta la **cartella H3-Chat completa** in una posizione scrivibile. Non separare `H3-Chat.app` dagli altri file.
3. Apri `H3-Chat.app`: l'interfaccia viene mostrata nel browser predefinito. Per fermare il servizio locale usa `Ferma-H3-Chat.command`.

Il primo pacchetto ha una firma locale ad hoc, senza notarizzazione Apple. Se macOS lo blocca, verifica di averlo scaricato dalla release ufficiale e usa **Impostazioni di Sistema → Privacy e sicurezza → Apri comunque**, seguendo la richiesta di macOS. Non disattivare Gatekeeper. Guida Apple: https://support.apple.com/102445 .

## Funzioni disponibili

- Chat e Assistant tramite API esterne, con chiavi nel **Portachiavi macOS**.
- LLM locali GGUF con llama.cpp, CPU o **Metal**. Collega i pesi dal Catalogo; usa modelli compatibili con la RAM del Mac.
- Progetti e RAG locali: importazione PDF/Word/testi, ricerca testuale e embedding GGUF, incluso EmbeddingGemma, sulla CPU. Il supporto Windows a Ovis e al runtime PyTorch di EmbeddingGemma 2 non è incluso in questo primo pacchetto.
- Slide, canvas, infografiche senza rendering locale CUDA, esportazioni HTML, PowerPoint, PDF e immagini del canvas. Il PDF usa il browser incluso.
- Servizi esterni configurati per immagini, video, voce e musica. I motori locali CUDA/NVIDIA non sono compatibili con questo pacchetto.

L'esecuzione locale di codice generato, Manim, LaTeX standalone e i motori generativi multimediali Windows non vengono abilitati senza un porting e un isolamento specifici per macOS. Le formule nel canvas continuano a essere visualizzate tramite KaTeX.

Il pulsante CPU mantiene il comportamento delle altre edizioni: disabilita la generazione multimediale e forza chat/Assistant sul dispositivo CPU o sul provider scelto. Per usare servizi multimediali esterni lascia la modalità normale GPU, anche quando il lavoro effettivo viene svolto dal server esterno.

## Dati e aggiornamenti

Conversazioni, account e collegamenti restano nella cartella `data`; i pesi scaricati in `models`. Prima di aggiornare attendi la fine dei lavori, ferma il servizio e fai una copia di `data`. Sostituisci i file dell'app con quelli della nuova cartella estratta, conservando dati e modelli. Non copiare i runtime binari da Windows sul Mac. Le chiavi API protette da Windows vanno reinserite nel Portachiavi del Mac.

## Build e verifiche

La build è eseguita su un runner macOS arm64. Python e llama.cpp sono archivi ufficiali con versione, dimensione e SHA-256 fissati in `scripts/macos-sources.json`; i wheel macOS sono installati solo da distribuzioni binarie con le versioni indicate in `scripts/macos-requirements.txt`. La build verifica avvio del servizio, API, Portachiavi, lettura documenti, RAG e PDF con i componenti effettivamente inclusi. Lo ZIP contiene il manifest SHA-256 di tutti i file e un rapporto di verifica; dati personali e modelli generativi non sono inclusi.
