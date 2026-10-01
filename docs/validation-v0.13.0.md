# Verifiche H3-Chat 0.13.0

Progetti/RAG, fonti web nei progetti, interprete numerico, Manim e server esterni
sono stati verificati in cartelle dati separate da quelle dell'utente.

- **188 test Python**: regressioni esistenti, migrazione del database, isolamento
  tra progetti, documenti modificati/cancellati, selezione fonti, citazioni inesistenti
  e letterali, percorso PDF → storyboard Manim, destinazione canvas, dati calcolati,
  salvataggio fonti web, limiti dell'interprete, dispositivi e memoria remota.
- **2 test JavaScript**, compilazione UI, controllo ABI del worker immagini e
  provenienza CRT locale. Nuovo bundle per installare il clone senza compilatori.
- **EmbeddingGemma Q8 reale su CPU**: modello scaricato e verificato con SHA-256,
  inferenza locale tramite llama-server, vettori di 768 dimensioni. Ricerca semantica
  e lessicale testate; il collaudo di isolamento usa anche vettori controllati.
- **PDF → LLM → MP4 reale**: estrazione di un PDF di due pagine, GGUF locale da 27B
  su CPU/CUDA con offload, storyboard di due scene con ricavi 1200, costi 300 e
  profitto 900, rendering Cairo 640 × 360 / 10 fps. Il piccolo Qwen3 0.6B ha prodotto
  un video valido ma ha omesso parti della richiesta: limite qualitativo documentato.
- **Manim reale CPU/Cairo e GPU/OpenGL** su RTX 5070 Ti: storyboard con testo,
  formula MathText, cerchio e grafico di `x**2`. Corrette incompatibilità della
  radice SVG e delle curve nel percorso OpenGL. Video decodificato con PyAV,
  fotogrammi e assi numerici controllati visivamente.
- **Interfaccia in browser**: progetti creati e fonti indicizzate, checkbox documenti,
  citazioni con estratto evidenziato, callout, codice evidenziato, LaTeX, Mermaid,
  calcolo reale, grafico numerico e MP4 nel canvas senza duplicazione nel corpo;
  download, collegamento Forge, server H3 avviato/arrestato, desktop e viewport
  390 × 844 senza overflow orizzontale. Nessun errore JavaScript. L'LLM di questa
  prova UI usa una risposta controllata; calcolo e Manim sono eseguiti realmente.
- **Server esterni tramite HTTP reale locale**: Images API JSON/multipart e Forge
  con fixture; H3 immagini, musica e video con coda seriale e generatori controllati;
  LLM SSE, autenticazione, assenza endpoint filesystem, annullamento del lavoro
  remoto e protezione DPAPI. Nessuna chiamata cloud a pagamento.
- **Pacchetto portabile**: manifest e SHA-256, estrazione in cartella nuova,
  interfaccia/launcher precompilati, worker CPU e stato iniziale, lettura PDF/Word,
  progetti e chiavi DPAPI. Componenti Manim/ASR/embedding restano opzionali: non
  sono inclusi nello ZIP base, i modelli non sono mai inclusi.

Il collaudo non certifica tutte le combinazioni di checkpoint e hardware.
Whisper CUDA e RAG CUDA hanno selezione e avvio integrati, ma non una nuova prova
di inferenza in questa release. Le nuove connessioni cloud non sono state provate
con credenziali dell'utente. Musica/video remoti richiedono H3, Images API richiede
risposte base64. Manim usa uno storyboard limitato e validato, non Python generale
o tutta l'API Manim. La correttezza semantica dei testi/scene resta legata all'LLM.
