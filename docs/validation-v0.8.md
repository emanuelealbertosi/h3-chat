# Verifiche H3-Chat 0.8.0

Ambiente: Windows x64, Python incorporato 3.13, RTX 5070 Ti 16 GB; inferenza musicale audio.cpp CUDA 12.8 e CPU AVX2.

- 79 test Python e 2 test del renderer superati. Copertura aggiunta: routing musica esplicito/automatico e negazioni, Assistant Off senza LLM installato, campi manuali, preset e limiti, modello/VAE in percorsi distinti, sidecar obbligatori, canvas senza duplicazione, stima GPU indipendente dalla chat, estrazione selettiva sicura e streaming WAV con Range/seek.
- Prova reale con Qwen 27B: Assistant ha preparato stile e testo nello stesso processo chat già caricato; il processo LLM è stato arrestato prima della musica in modalità A richiesta.
- YuE2-3B Q8, preset H3-Music completi: WAV stereo 48 kHz, 87,439 secondi, 32 passi, CFG 1, seed 831001, pianificazione Full; nessun troncamento. Prova di integrazione e contenuto audio non silenzioso, non valutazione soggettiva della qualità musicale.
- Seconda generazione nello stesso worker: 7,999 secondi con limite deliberato a 200 token e 2 passi; flag di troncamento rilevato. Il ritorno al modello chat ha arrestato il worker musicale.
- CPU reale: WAV stereo 48 kHz, 7,999 secondi con limite 200 token/2 passi; troncamento correttamente rilevato. Non è un benchmark del preset completo su CPU.
- Browser Edge: durata WAV, seek a 30 secondi, link download, Music/Assistant e campi persistenti per chat, output solo nel canvas quando attivo, preset salvati/ripristinati, selettore filesystem e layout mobile 430 px. Nessun errore JavaScript rilevato.

- Pacchetto ZIP estratto in una cartella con spazi e accenti: verifica del manifest, installazione CUDA dagli archivi verificati, generazione reale CPU e CUDA via coda della chat, Assistant Off senza LLM, canvas e avviso di troncamento. Python e DLL privati, PATH limitato a Windows/System32.

Il test con pesi reali è ripetibile con `tests/real-music-smoke.py`, fornendo modello e VAE. I pesi e le chat di collaudo non sono inclusi nei pacchetti pubblici. Le GPU diverse dalla RTX 5070 Ti non sono state collaudate fisicamente. Italiano sperimentale, nessun supporto Vulkan per YuE2; niente analisi audio o editing di brani caricati.
