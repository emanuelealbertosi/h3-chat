# Steering locale Qwen27B — 27 ottobre 2026

Sono disponibili due percorsi opzionali, spenti per default e salvati per modello:

- **Control vector additivo**: GGUF con direzioni F32 per layer. L'intensità
  modifica le attivazioni; 0 è neutro. Un file projectivo GLP non è additivo.
- **LoRA GLP-49 · rango 1**: adapter GGUF convertito dal PEFT ufficiale, con
  `alpha=1`. H3 lo applica con `--lora`, conservando i pesi del modello originale.
  La scala è fissa a 1; l'intervallo dei layer riduce la copertura estraendo
  soltanto i relativi tensori in una copia di cache. Non vengono rinumerati.

Entrambi richiedono Qwen `qwen35` 27B: embedding 5120 e 64 layer principali.
Layer zero e blocco MTP sono esclusi; intervallo consentito 1–63. Non sono
supportati dai collegamenti API remoti. Cambiare file, modo o intervallo ricarica
il processo gestito alla richiesta successiva. Disattivare ripristina il percorso
normale senza alterare modello o preset restanti.

## GLP-49

Il repository dell'autore richiede l'accettazione delle condizioni Hugging Face.
Nessun peso viene incluso nel codice o scaricato automaticamente dall'app.
Scarica `adapter_config.json` e `adapter_model.safetensors` dopo l'autorizzazione,
poi usa il convertitore offline senza PyTorch e senza un secondo modello:

```text
runtime/python/python.exe -X utf8 scripts/convert-glp-lora.py --adapter CARTELLA_ADAPTER --output CARTELLA_MODELLI/glp49-qwen35-rank1.gguf
```

Il convertitore conserva i byte F32, controlla rango, dimensioni, offset e tutte
le 252 matrici. Il loader controlla architettura, coppie A/B, blocchi ibridi,
valori finiti, file completo e alpha. Una copia identificata dal contenuto entra
nella ricetta di residenza. File incompatibili producono un errore prima di
interrompere un modello già pronto.

Il formato **GGUF projectivo** pubblicato dallo stesso autore richiede un altro
operatore e non è accettato come vettore additivo. L'integrazione H3 usa invece
l'adapter LoRA convertito; non cambia il runtime ottimizzato né le sue DLL.
L'autore avverte che aumentare alpha può riflettere la componente invece di
rimuoverla: H3 impedisce una scala GLP diversa da 1.

## Prove effettuate

Il GGUF ISTA-DASLab `Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf` locale, da
12.120.016.960 byte, è stato provato realmente su GPU. GLP-49 è stato scaricato
con autorizzazione umana alla revisione `5f1be31cfde653f24fe74c71047433012b8ede9e`.
Il GGUF convertito è da 8.533.280 byte; SHA256:
`6f5087bfb2db362ec4cfd0aba898c7152428ae1232d0c5fc2b8b54d979dee4a6`.

Standard e profilo ottimizzato MTP2 hanno superato controlli brevi di aritmetica,
JSON strutturato, scelta di un tool, grounding su una fonte chiusa, italiano e
scrittura narrativa. Il motore ha confermato l'adapter attivo a scala 1 tramite
la sua API. La prova verifica caricamento e compatibilità dei compiti campione;
non misura una rimozione universale dei rifiuti né certifica qualità a 80–128K.
L'intensità corretta di un additivo non va trasferita a GLP.

È stato anche ricavato un **vettore additivo locale di direttezza** dall'esatto
ISTA, con 24 coppie di prompt innocui. Il generatore è stato compilato allo stesso
commit del motore, correggendo la raccolta delle uscite fisiche 1–63 del Qwen
ibrido. Intensità 0,1 ha superato le prove brevi Standard e MTP2; intensità 1 ha
prodotto una risposta vuota ed è stata scartata. Questo esperimento non viene
presentato come un'abliteration verificata.

Le prove sono state eseguite con un Engine e dati temporanei isolati: nessuna
preferenza di produzione è stata attivata implicitamente, nessuna chat o
credenziale è stata usata per il confronto. I test sono su Windows/RTX 5070 Ti;
non rappresentano un collaudo GPU fisico Mac/Linux.

## Fonti primarie

- [ISTA-DASLab, modello e quantizzazioni](https://huggingface.co/ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF)
- [GLP-49: adapter, scala e metodo](https://huggingface.co/msuiche/Qwen3.8-27B-abliterated-cyber-GLP-49)
- [llama.cpp: generatore di vettori](https://github.com/ggml-org/llama.cpp/tree/master/tools/cvector-generator)
- [UCVG: vettori e limiti](https://github.com/Egor4More/ucvg.cpp)
