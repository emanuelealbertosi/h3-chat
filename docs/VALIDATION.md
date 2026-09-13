# Verifica della versione 0.2.0

Verificata su Windows il 13 settembre 2026.

- 19 test Python superati: funzioni di base della chat, snapshot dei lavori, canvas, HTTP, download, riconoscimento GGUF e mmproj, ambiguità dei proiettori, recupero dopo rimozione del mmproj, metadati incompleti, livelli thinking e separazione dello stream, scenari di memoria OK/offload/OOM/non rilevabile.
- 2 test JavaScript superati: coordinate e serie dei grafici preservate, opzioni eseguibili rifiutate.
- Browser Edge desktop e mobile: cinque livelli Think salvati, selezione del modello vision e disabilitazione del thinking non supportato, avvisi non vision nel composer e nella risposta, letture reali RAM/VRAM nel setup, catalogo e scansione locale. Nessun errore JavaScript né overflow orizzontale.
- Qwen3 0.6B su CPU, Think Low: risposta reale corretta al prodotto 17 × 19.
- Qwen3 0.6B su CPU, Think High: osservati eventi di ragionamento separati con budget massimo di 512 token, artefatto nel canvas e messaggio standard nella chat. Il testo di ragionamento non entra nel documento né nel corpo.
- SmolVLM locale: GGUF e mmproj in una cartella dedicata, rilevamento automatico e avvio reale di llama-server su CPU con proiettore caricato e health check riuscito. Pesi temporanei collegati ai file già presenti, poi rimossi dal test.
- Hardware reale: Ryzen 5 3600, RAM e RTX 5070 Ti rilevati tramite API Windows e nvidia-smi. VRAM libera misurata, senza sommarla alla RAM condivisa. Valutazioni AMD/Intel, contatori WDDM e più GPU non collaudati su hardware fisico di tali tipi: i dati mancanti producono uno stato non determinabile.

Le verifiche della versione 0.1 comprendevano già Markdown, codice, LaTeX, grafici e Mermaid, export Word/PDF/PNG con controllo visivo e avvio del pacchetto estratto. I renderer e gli esportatori restano invariati nella 0.2.

L'inferenza immagini Stable Diffusion/FLUX e i backend CUDA/Vulkan devono ancora essere collaudati sulle rispettive configurazioni hardware. I valori di memoria sono stime preventive, non limiti o garanzie; anche un esito OK può essere superato da driver, buffer o altre applicazioni. La qualità delle risposte e della formattazione resta dipendente dal modello selezionato.
