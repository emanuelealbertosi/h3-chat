# H3-Chat 0.13.2 — cambi modello e MiniMax H3

## Riuso del motore immagini

Con modalità A richiesta e cache file attiva, Ming/Qwen scarica i pesi tramite IPC
e conserva il processo Python già inizializzato. Non è un secondo modello residente:
le librerie usano ancora RAM e il contesto CUDA una piccola quota di VRAM.
Cache disattivata, Libera memoria, arresto dell’app o cambio CPU/GPU chiudono il
processo. Un errore nello scaricamento forza la chiusura prima del modello successivo.

Prova reale su Windows, RTX 5070 Ti, Qwen Image 2.1 INT8 e encoder Qwen3-VL 8B INT8:

- Generazione PNG 256×256, un passo, CFG 1 sulla GPU.
- Scaricamento dei pesi: 0,56 secondi, confermato dal worker.
- Nuovo caricamento con lo stesso PID: circa 1,5 secondi, contro 16,2 secondi
  di avvio completo e lettura iniziali nella stessa prova.
- La generazione iniziale completa è durata circa 94 secondi: quei 1,5 secondi
  non comprendono trasferimenti GPU, encoding, campionamento e decodifica.
  Il primo avvio e il ricaricamento del processo LLM restano completi.

La prova verifica uno scaricamento reale e il ricaricamento dello stesso processo;
il passaggio attraverso un LLM intermedio è coperto dai test di proprietà del pool.
I risultati variano con file, disco, driver, disponibilità RAM e contesto GPU.

## Arresto MiniMax H3

L’evento Windows originale segnala `0xC0000005` in `torch/lib/c10.dll`.
La riproduzione con faulthandler identifica il trasferimento CUDA→CPU dei tensori
quantizzati dell’encoder durante `ModelPatcher.unpatch_model`.
Disabilitare offload asincrono/pinned memory non risolveva la riproduzione e non
è una modifica conservata nella release.

La correzione libera encoder e VAE dopo aver costruito il condizionamento, quindi
carica il diffusore. Dopo il campionamento libera anche il diffusore e ricarica
il VAE video/audio richiesto dalla decodifica. I riferimenti e il condizionamento
restano presenti; il calcolo resta CUDA. Gli stadi completati non vengono riportati
in RAM attraverso quel percorso non sicuro. Offload disattivato conserva i componenti.

Prova reale con Hybrid INT8, encoder MiniMax Qwen3-VL 32B NVFP4/AWQ, VAE video
INT8/ConvRot, VAE audio FP32 e un PNG di prova come fotogramma iniziale:

- MP4 generato e decodificabile: 24 fotogrammi, 608×352, un secondo, 24 fps, audio
  32 kHz; due passi, offload attivo.
- Il caricamento del diffusore supera il punto che prima causava l’arresto nativo.
- Circa 131 secondi totali a freddo; non è una promessa di generazione immediata.
- Durata 15 secondi, risoluzione 0,7 MP e 12 passi restano i default, ma questa
  prova di regressione è intenzionalmente breve e non verifica quel carico completo.

Test Python dedicati verificano scaricamento, riuso, cambio backend, stop,
annullamento e fallback, rilascio dei componenti e messaggi di uscita nativa.
I test completi sono eseguiti anche dalla build Windows su GitHub.
