# Motore musicale autonomo

H3-Chat 0.8.0 usa un worker C++ privato, con messaggi JSON via stdin/stdout. Il processo appartiene alla coda seriale dell’app; annullamento, cambio modello e chiusura arrestano solo i processi avviati da H3-Chat. Non ci sono chiamate a H3-Music, ComfyUI, LM Studio o servizi musicali remoti.

## Provenienza e riproduzione

- Wrapper: `native/music/worker.cpp`, MIT come H3-Chat.
- Inferenza: [audio.cpp](https://github.com/0xShug0/audio.cpp/tree/13c4192a28d6a212f075c4cbefc5e4983e6ed52a), commit `13c4192a28d6a212f075c4cbefc5e4983e6ed52a`, Apache-2.0.
- Archivio sorgenti: SHA-256 `7bdd528f8f0ec176823fb478ee7f03dbb8fdbd628f63f669ff281fe100b5a2dd`.
- Estensione locale derivata da H3-Music: `native/music/h3-artifacts.patch`, per salvare spartito, codici e flag di troncamento. Il worker usa una richiesta normale; nessuna modalità plan-only nell’interfaccia.
- Preset e pipeline riprendono H3-Music. L’Assistant è invece l’LLM già selezionato in H3-Chat.
- Catalogo pesi: [audio-cpp/Yue2-3B-GGUF](https://huggingface.co/audio-cpp/Yue2-3B-GGUF/tree/a58a47b18099d565153b14f644e6f47bf287ccd8), revisione fissata nel catalogo con SHA-256 per ogni file. Licenza CC BY-NC 4.0.

Da PowerShell, con Visual Studio Build Tools C++, CMake, Ninja, Git e Python:

```powershell
./scripts/build-music-runtime.ps1 -Backend cpu
./scripts/build-music-runtime.ps1 -Backend cuda -CudaToolkit 'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.8'
python scripts/package-music-runtime.py
```

Senza `-AudioSource`, lo script scarica l’archivio fissato, verifica l’hash e applica/verifica la patch. Per una sorgente già estratta usare `-AudioSource`. Viene compilata soltanto la famiglia YuE2; CPU x64 AVX2 senza ottimizzazioni specifiche della macchina di build. CUDA include PTX compute 7.5 per GPU compatibili e codice nativo 12.0. Serve un driver NVIDIA compatibile con CUDA 12.8; le prove reali sono su RTX 5070 Ti. Altre GPU non sono state collaudate fisicamente.

`music-notices.py` conserva le licenze upstream e registra la provenienza. Il pacchetto portatile include il worker CPU e i redistributable CRT privati. Il runtime CUDA scarica il worker verificato dalla release H3-Chat e cudart/cuBLAS dai redistributable ufficiali NVIDIA 12.8.1: hash e lista precisa dei DLL/licenze estratti sono in `runtimes.json`. Non è necessario installare CUDA Toolkit sul computer dell’utente.

## Modelli esterni e memoria

Il main GGUF deve contenere i tensori YuE2, il VAE quelli del decoder audio. Il tokenizer `yue2-qwen.tiktoken` e i file `yue2-model-config.json`, `yue2-generation-config.json`, `yue2-vae-config.json` devono essere in `sidecars/` accanto al main GGUF. Il VAE usa il percorso assoluto scelto dall’admin, anche in un’altra cartella. Non vengono copiati pesi o configurazioni, né eseguito codice dalla cartella dei modelli.

Il contesto musicale è indipendente da quello chat. Cambiare backend/thread, pesi o sidecar ricrea la sessione; cambiare seed e campionamento non richiede un altro processo. Due richieste consecutive riutilizzano il worker. La pipeline alterna internamente AR, NAR e VAE: Residenti non significa che tutte queste componenti restino contemporaneamente sulla GPU. A richiesta arresta il worker precedente prima di caricare il successivo. La cache RAM è la stessa cache di file mappati e recuperabili già usata dalla chat.

I brani sono in `data/outputs/<job>/audio.wav`; composizione, parametri, score e flag restano accanto al WAV per diagnosi e riproducibilità. Il player usa richieste HTTP Range al server locale. Gli audio non diventano riferimenti vision o immagini di editing. Solo metadati e composizione testuale entrano nel contesto successivo.
