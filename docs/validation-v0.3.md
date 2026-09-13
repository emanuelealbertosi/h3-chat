# Verifica H3-Chat 0.3.0

Verifica locale su Windows x64, Python embedded 3.13.15, CPU Ryzen 5 3600.

- 26 test Python: include riuso del contesto, scaricamento al cambio, tre modelli residenti, annullamento del contesto attivo, invalidazione per configurazione/file, cache limitata e disattivabile, stima cumulativa con deduplicazione crea/edit, router immagini senza caricamento LLM e regressioni di vision/Think/canvas.
- 2 test JavaScript del rendering numerico.
- Browser Edge: salvataggio delle due modalità e della cache, stima con due modelli distinti quando crea/edit coincidono, due risposte reali Qwen3 con lo stesso PID, rilascio manuale, desktop e larghezza mobile 390 px senza overflow.
- Worker nativo compilato da sorgente MSVC x64, ABI verificata contro le DLL incluse di stable-diffusion.cpp 7f410a3.
- Ciclo reale su CPU: Qwen3 0.6B → creazione SD 1.5 FP16 → editing dello stesso output → Qwen3. Il PID immagini resta identico fra crea/edit e termina prima di ricaricare la chat. Output PNG 256×256; un passo per limitare il costo della verifica, senza valutazione della qualità artistica.
- Modalità residenti su CPU: Qwen3 e SD 1.5 caricati contemporaneamente; ritorno alla chat senza nuovo processo; Libera memoria termina entrambi e chiude i mapping.

Checkpoint della prova immagini: conversione FP16 di SD 1.5 distribuita da Comfy-Org/stable-diffusion-v1-5-archive, revisione 9cfd069101959ca3828bf9c04a4419870832b74f, SHA-256 e9476a13728cd75d8279f6ec8bad753a66a1957ca375a1464dc63b37db6e3916. Pesi, chat e immagini di prova non sono inclusi nel pacchetto.

Limiti: il riuso reale è verificato su CPU. CUDA/Vulkan residenti e FLUX con quattro riferimenti non sono stati eseguiti su hardware in questa verifica. Il protocollo conserva ordine e numero dei riferimenti e la collocazione GPU usa l'API ufficiale del motore. Le stime RAM/VRAM restano euristiche; nessuna promessa di assenza di OOM o di accelerazione costante dalla cache.
