# Verifiche H3-Chat 0.6.0

Eseguite il 13 settembre 2026 su Windows. Motori invariati: llama.cpp b10809 e stable-diffusion.cpp 7f410a3; worker immagini aggiornato.

- **57 test Python** superati con Python incluso: regressioni precedenti, cartelle LoRA multiple/ricorsive, omonimi, file non LoRA e malformati, unità mancanti, famiglie sconosciute/incompatibili, limiti dei pesi, percorsi non autorizzati nella selezione, snapshot dei lavori, file modificati dopo invio, filtri per modello e peso zero, metadati dei messaggi, parametri di inferenza e stime di memoria.
- Preset Anima Base/Aesthetic 30 step/CFG 4 e Turbo 8 step/CFG 1, componenti richiesti, sola generazione da testo, personalizzazioni per modello, precedenze, seed casuale/fisso, valori non validi e persistenza dei flag Avanzate.
- Regressione del flow shift: Anima e FLUX mantengono il default automatico dell'API; lo zero forzato causava immagini uniformi. Qwen Image Edit conserva il valore 3. Una prima prova Anima ha rilevato il difetto attraverso l'ispezione dell'immagine; è stata scartata e ripetuta dopo la correzione.
- **2 test JavaScript** per i grafici numerici; compilazione dell'interfaccia. I sampler e scheduler esposti sono stati confrontati con le funzioni native di conversione nome/enum, senza discrepanze. Worker ricompilato e protocollo/ABI verificati.
- **Edge desktop e 390 px**: riepilogo dei preset con controlli nascosti, flag Avanzate, modifica e persistenza per modello, ritorno ai valori generali, selezione di due cartelle esterne, tre LoRA distribuiti su due destinatari, famiglie incompatibili disabilitate, modifica del peso durante l'aggiornamento automatico, cambio chat e riapertura, dettagli immagini visibili/nascosti. Nessun errore JavaScript o overflow orizzontale. Le prove dell'interfaccia usano fixture strutturali; non sono inferenza con i LoRA simulati.

## Inferenza reale Anima e LoRA

Anima Turbo 1.1 Q4_K_M, encoder Qwen3-0.6B **Base** Q4_K_M e VAE Qwen Image, nelle revisioni e negli hash del catalogo. Componenti e LoRA collegati fuori dalla cartella dell'app: nessuna copia e hash originali invariati.

Prova su Ryzen 5 3600, CPU con 6 thread, **512 × 512, 8 step, CFG 1, Euler, scheduler discrete, seed 123456**. Stesso prompt con una casa, uno stagno, fiori e alberi per tutte le immagini.

Adapter reale: [Anima highres aesthetic boost ufficiale](https://huggingface.co/circlestone-labs/Anima-Official-LoRAs/blob/5b652129e03e0ca847de8bbf52d957a9860c59a7/anima-highres-aesthetic-boost.safetensors), peso 1; SHA-256 `db5b2dcc4e1afa215058b7a85fb9377124c2e9aabd48c25e595af7199207c299`.

| Generazione | SHA-256 PNG |
|---|---|
| baseline | `a466a42f9362366187cbe0649d8e068826e6fef29d4a0aa85fd7cfb58a5565cf` |
| with-lora | `86783ec8d2291f231d182227f4248eb785fb5925255f4d0b0c9e37e68d2aff40` |
| removed-lora | `a466a42f9362366187cbe0649d8e068826e6fef29d4a0aa85fd7cfb58a5565cf` |

L'immagine con LoRA è diversa. Dopo la rimozione, il PNG torna identico alla baseline. **Un solo processo e un solo contesto per le tre generazioni**, con utilizzi 1 → 2 → 3. Controllata anche la resa visiva delle immagini, oltre al completamento del protocollo e agli hash.

## Ripetere le verifiche

`python -m unittest discover -s tests` e `npm test` eseguono le verifiche automatiche senza pesi. `python scripts/check_native.py` controlla il worker con i motori CPU installati.

Per il browser, prepara esclusivamente dati di prova con `python tests/prepare-image-settings.py`, avvia `python app.py --port 8788 --data work/qa-v06-data` e usa `node tests/browser-image-settings.mjs`. `H3_PLAYWRIGHT` può indicare un'installazione Playwright disponibile; serve Edge. Non usare una copia con conversazioni personali.

`python tests/real-anima-smoke.py --weights CARTELLA` ripete il confronto CPU. La cartella deve contenere i tre file del catalogo con i nomi originali e `anima-highres-aesthetic-boost.safetensors`. La prova non scarica i pesi e usa dati separati in `work/real-anima-test`.

## Limiti del collaudo

Inferenza reale nuova verificata su **CPU con un LoRA Anima**. Selezioni multiple e destinatari diversi sono verificati nelle API e nell'interfaccia; questa prova non certifica ogni combinazione di adapter, formato e architettura. CUDA/Vulkan, Anima Base/Aesthetic, FLUX multi-riferimento e Qwen Image Edit richiedono prove sulle rispettive configurazioni. Le stime RAM/VRAM restano preventive, senza garanzia di assenza di OOM.

Il pacchetto portatile comprende Python, motori CPU, launcher, script Installa/Avvia/Ferma, interfaccia e documentazione. Conversazioni, pesi, LoRA, cache e registri di prova sono esclusi; ogni file distribuito è elencato in `FILES-SHA256.json`.
