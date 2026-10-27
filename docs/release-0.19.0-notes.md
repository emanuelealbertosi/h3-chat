H3-Chat 0.19.0 aggiunge la modalità **Agente** e allinea Windows, macOS Apple Silicon e Linux x64.

- **Agente opzionale:** strumenti H3, file, codice, esecuzione, ricerche web, download e installazione di LoRA compatibili. Assistant rimane disponibile.
- **H3 / Sandbox / Globale**, Autoapprova con avviso e preferenze dedicate per budget, passaggi, tempo, chiamate e ruoli di preparazione. Le conferme amministratore e le chiavi API restano separate.
- **Preparazione con più ruoli:** stesso LLM, chiamate in sequenza, budget condiviso e un solo coordinatore che esegue strumenti.
- **Immagini e video:** conservazione di modello, seed, formato e megapixel; MOSS Turbo esplicito; profilo FastH3 Omni corretto e provato su GPU.
- **Slide:** correzioni al numero della pagina da modificare, ai formati immagini e alla separazione tra istruzioni del motore e contenuti.
- **Mac Apple Silicon:** CPU/Metal, API esterne, documenti, RAG, PDF, Manim e LaTeX. CUDA escluso; firma ad hoc, senza notarizzazione Apple.
- **Linux x64:** base CPU/API, componenti Vulkan/NVIDIA, documenti, PDF isolato, Manim e LaTeX; collaudi nativi Ubuntu e Kali. L'eventuale eccezione AppArmor per bubblewrap richiede una scelta esplicita nell'installer.
- **Windows senza GPU:** resta disponibile l'installazione API con RAG locale opzionale.

Ogni pacchetto ha checksum SHA-256 e rapporto di verifica. Pesi generativi, chat, credenziali e dati personali non sono inclusi.

**Aggiornamento:** termina i lavori e ferma l'app. Conserva una copia della cartella `data` e della vecchia installazione; estrai il nuovo pacchetto in una cartella nuova e trasferisci i dati prima dell'avvio. Mantieni validi i percorsi dei modelli esterni. Non avviare l'app dentro l'archivio.

**Limiti:** l'Agente non controlla ancora visivamente mouse e tastiera; i ruoli multipli non sono esecuzioni concorrenti con modelli diversi. Lo steering locale è manuale, sperimentale e spento per default: nessun vettore è incluso e non è stato verificato un vettore pubblico per l'esatto checkpoint ISTA.

Dettagli: [novità e limiti](https://github.com/emanuelealbertosi/h3-chat/blob/main/docs/release-0.19.0.md), [guida Agente](https://github.com/emanuelealbertosi/h3-chat/blob/main/docs/agent.md), [Linux](https://github.com/emanuelealbertosi/h3-chat/blob/main/docs/linux.md), [Mac](https://github.com/emanuelealbertosi/h3-chat/blob/main/docs/macos.md).
