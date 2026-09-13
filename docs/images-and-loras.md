# Immagini, preset e LoRA

## Preferenze e Avanzate

In **Impostazioni → Preferenze → Impostazioni immagini** scegli il modello. La vista normale mostra il riepilogo dei valori; **Avanzate** apre risoluzione, step, CFG, sampler, scheduler, seed, negative prompt e intensità img2img di Stable Diffusion.

Le personalizzazioni sono salvate **per modello** e hanno precedenza sui preset del profilo e sui valori generali. I valori generali sono usati dove il modello non dichiara un proprio valore. **Ripristina predefiniti del modello** elimina le sue personalizzazioni. Nascondere Avanzate conserva i valori salvati; non ripristina nulla. Le modifiche valgono per i messaggi successivi: i lavori già inviati mantengono la loro configurazione.

| Profilo | Step iniziali | CFG iniziale | Sampler automatico |
|---|---:|---:|---|
| Stable Diffusion / SDXL | 20, dalle Preferenze | 7 | Scelto dal motore |
| FLUX.2 klein distillato | 4 | 1 | Euler |
| Qwen Image Edit | 20, dalle Preferenze | 2,5 | Euler |
| Anima Base / Aesthetic | 30 | 4 | Euler |
| Anima Turbo | 8 | 1 | Euler |

La risoluzione iniziale segue il profilo hardware (512 × 512 nel profilo low VRAM), con personalizzazione per modello. Scheduler iniziale automatico, seed `-1` casuale, negative prompt vuoto; intensità img2img SD `0,65`. L'intensità non controlla l'editing semantico di FLUX/Qwen. Alcuni parametri hanno effetto solo nelle modalità supportate dal modello; per esempio CFG 1 normalmente non usa il ramo negative.

Il flag **Avanzate sotto il composer della chat** mostra i parametri registrati per le immagini: risoluzione, step, CFG, sampler, scheduler, seed effettivo e LoRA applicati. Il seed casuale viene risolto prima dell'inferenza e salvato; sampler e scheduler automatici sono riportati dal motore nativo. Il flag vale anche per i messaggi precedenti che possiedono questi dati. Le vecchie immagini senza metadati non vengono ricostruite artificialmente. La ripetibilità dipende anche da pesi, backend, versione e riferimenti.

## Anima

Il catalogo comprende **Anima Turbo 1.1 Q4**, con i tre componenti scaricati e verificati tramite SHA-256. Per file già presenti usa **Catalogo modelli → Collega un modello → Anima Base / Aesthetic** oppure **Anima Turbo**:

1. Diffusore Anima GGUF o safetensors.
2. Encoder **Qwen3-0.6B Base**, anche GGUF. Il modello chat Instruct e il mmproj non lo sostituiscono.
3. **VAE Qwen Image**.

Ogni componente può rimanere nella sua cartella originale. Questi profili generano immagini da testo; non sono proposti come modelli di editing o vision della chat. I valori di partenza seguono la [scheda ufficiale Anima](https://huggingface.co/circlestone-labs/Anima) e il caricamento usa il [supporto Anima di stable-diffusion.cpp 7f410a3](https://github.com/leejet/stable-diffusion.cpp/blob/7f410a3/docs/anima.md). La licenza del modello è indicata nel catalogo ed è distinta da quella dell'app.

## Cartelle LoRA e selezione nella chat

In **Preferenze → Cartelle LoRA** puoi collegare fino a 20 cartelle, su una o più unità. **Sfoglia** e **Usa questa cartella** registrano il percorso. Salva le Preferenze, poi apri **LoRA** accanto al pulsante degli allegati in chat. La scansione include le sottocartelle, con limiti per non esplorare interi dischi; se raggiunti, compare un avviso che invita a scegliere cartelle più precise. Le unità scollegate restano elencate con un avviso.

- Scegli il **modello destinatario** tra quelli assegnati a creazione ed editing.
- Seleziona fino a **8 LoRA** in totale e imposta il peso di ciascuno, da **−2 a 2**. Il peso iniziale è **1**; **0** disattiva l'adapter. Il pulsante × lo rimuove.
- I LoRA rimangono selezionati nella singola chat fino alla rimozione. Puoi associare adapter diversi ai due modelli immagini.
- Il router applica soltanto quelli associati al modello effettivamente usato. I LoRA assegnati all'altro modello o con peso 0 sono indicati come non applicati. Le normali risposte testuali non li usano.
- Se creazione ed editing usano lo stesso modello, condividono lo stesso destinatario e caricamento.

La famiglia è letta dai metadati, quando dichiarata. Una famiglia certamente incompatibile è disabilitata; **Famiglia non dichiarata** richiede di scegliere il modello per cui il LoRA è stato addestrato. Anche i LoRA ufficiali possono non includere questo metadato: il motore verifica poi il caricamento dei tensori. Il profilo storico SD/SDXL generico non distingue le due famiglie; per nuovi collegamenti SDXL è disponibile il profilo esplicito.

Sono indicizzati file **safetensors con coppie LoRA standard** (`lora_down/up` oppure `lora_A/B`). Non sono convertitori per checkpoint pickle, LoHa/LoKr, file Diffusers sparsi o LoRA LLM. La compatibilità dipende anche dall'architettura e dal formato supportato dal [motore incluso](https://github.com/leejet/stable-diffusion.cpp/blob/7f410a3/docs/lora.md); non è garantita dal solo nome del file.

I pesi originali non vengono copiati né modificati. Gli adapter sono applicati durante l'inferenza, con rimozione della selezione precedente a ogni generazione; cambiare peso o selezione normalmente riusa il modello base. Se un file già usato cambia, il contesto viene ricaricato. Un file rimosso o cambiato dopo l'invio ferma quel lavoro con una spiegazione.

Le stime di memoria includono un margine per i LoRA selezionati. **A richiesta** conserva un solo modello alla volta; **Residenti** conserva quelli scelti nel Setup. Le selezioni correnti per chat sono nel profilo locale del browser; i LoRA dei messaggi inviati restano anche nella cronologia, recuperabili con **Riutilizza**. Non sono sincronizzati automaticamente tra browser diversi.
