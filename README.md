# H3-Chat

Chat multimodale locale per Windows, con lo stile avorio e verde petrolio delle app H3. Una sola conversazione per testo, codice, immagini, formule, grafici e diagrammi. I motori sono gestiti dall'app; non servono Ollama, LM Studio, ComfyUI, chiavi API o abbonamenti.

## Installazione

**Pacchetto Windows:** scarica [H3-Chat-0.2.0-windows-x64.zip](https://github.com/emanuelealbertosi/h3-chat/releases/download/v0.2.0/H3-Chat-0.2.0-windows-x64.zip) dalla [release v0.2.0](https://github.com/emanuelealbertosi/h3-chat/releases/tag/v0.2.0), estrailo in una cartella scrivibile e apri `H3-Chat.exe`. Il pacchetto include Python, i motori CPU e tutte le librerie dell'interfaccia. Non occorrono privilegi di amministratore. Non avviare l'app direttamente dentro lo ZIP.

**Primo avvio:** apri **Impostazioni → Setup**, scegli hardware e modelli. Il catalogo scarica i pesi e tutti i componenti richiesti, controllando dimensione e SHA-256. I backend GPU si installano dallo stesso setup. Dopo i download, inferenza, interfaccia e documenti funzionano offline.

**Dai sorgenti:** `Installa-H3-Chat.bat` prepara Python integrato e il launcher. Se manca il bundle dell'interfaccia, servono Node.js 22+ e npm per compilarlo. Usa la release ZIP per evitare questo passaggio.

La finestra desktop usa Microsoft Edge in modalità app, normalmente già presente in Windows 10/11. Se Edge manca, la chat si apre nel browser predefinito; l'export PDF richiede Edge. Chiudere la finestra lascia finire il lavoro corrente. `Ferma-H3-Chat.bat` arresta il servizio e i processi di inferenza posseduti dall'app.

## Un unico prompt

- «Scrivi una funzione Python…» → risposta con codice evidenziato.
- «Crea un'illustrazione botanica…» → motore di generazione immagini.
- «Combina queste quattro foto in una scena…» → motore di modifica, con i riferimenti numerati nell'ordine degli allegati.
- «Leggi questo grafico e ricostruiscilo…» → modello vision, dati e renderer numerico.
- «Spiegami questa formula…» → testo e LaTeX.

Non ci sono modalità da selezionare nel composer. Le richieste esplicite più comuni sono riconosciute direttamente; quelle ambigue sono classificate dal modello chat con uno schema JSON vincolato. I modelli piccoli possono interpretare male richieste complesse: per codice, routing e analisi densa scegli un modello più capace dal setup.

Le tre selezioni nelle impostazioni sono **chat/router/vision**, **creazione immagini** e **modifica immagini**. Un solo modello è assegnato a ciascun ruolo. Chat e immagini non restano contemporaneamente in memoria: il processo LLM viene terminato prima di avviare quello immagini. A fine richiesta viene rilasciato anche il motore attivo. La coda è globale e seriale, con interruzione del lavoro e registrazione degli errori.

## Vision e modelli locali

Il composer indica sempre **Vision attiva** oppure **Non vision**, con un avviso se manca il proiettore. Il nome commerciale del modello non basta: l'app verifica la presenza del `mmproj`. Nei modelli del catalogo usa esclusivamente il componente associato; non prende proiettori di altri modelli dalla cache condivisa. Se il proiettore viene rimosso da un modello già installato, i pesi verificati restano utilizzabili per il testo e il catalogo permette di completare di nuovo il download.

Per un GGUF locale, crea una cartella dedicata come `models/local/NomeModello/` e inserisci i pesi insieme al **solo mmproj compatibile**. Apri Catalogo modelli → Rileva modelli locali e scegli il modello nel setup. I metadati GGUF vengono letti senza eseguire codice; il proiettore presente nella stessa cartella viene passato automaticamente al motore. Se ci sono più proiettori non viene scelto arbitrariamente. La presenza del file non certifica l'abbinamento: un proiettore incompatibile viene rifiutato dal motore. Il GGUF deve essere supportato dalla versione integrata di llama.cpp. I file locali non sono scaricati né verificati contro un hash del catalogo.

Senza vision, la chat testuale continua a funzionare e le risposte conservano l'indicazione. Una richiesta di lettura delle immagini viene fermata con un messaggio esplicito; creazione e modifica artistica continuano a usare il proprio motore immagini.

## Thinking nella chat

Il menu **Think** offre **Off, Low, Med, High e XHigh**. È abilitato solo se i metadati/template del modello indicano un thinking compatibile (oppure per i modelli del catalogo con supporto noto). Qwen3 lo supporta; SmolVLM e Qwen2.5-VL del catalogo non lo espongono.

I livelli riservano rispettivamente 0%, 12,5%, 25%, 50% e 75% del limite di risposta al ragionamento, lasciando spazio al testo finale. Con 1024 token: 0, 128, 256, 512 e 768. Il valore è un budget massimo, non un numero di token obbligatorio e non una garanzia di qualità. Per template con livelli nativi viene inviato anche il livello supportato; XHigh usa il livello nativo High quando il template non accetta XHigh, mantenendo il budget più ampio. Per artefatti lunghi aumenta la risposta massima e il contesto nelle Preferenze.

La scelta è salvata e fotografata in ogni richiesta, anche con canvas attivo. Il router usa sempre Think Off per evitare lavoro aggiuntivo prima di una generazione immagini. La fase thinking è indicata nello stato; la risposta e il canvas ricevono solo il contenuto finale, senza i token di ragionamento.

## Verifica preventiva della memoria

Il setup mostra CPU e thread, RAM totale/libera e GPU con VRAM totale/libera quando il driver la espone. NVIDIA usa `nvidia-smi`; su Windows DXGI rileva anche AMD/Intel, e i contatori WDDM integrano la memoria libera quando disponibili. La RAM condivisa delle GPU integrate non viene sommata alla VRAM dedicata. Più GPU o contatori mancanti producono una stima non determinabile, non un falso “OK”.

Ogni modello selezionato ha una valutazione separata, perché i motori lavorano uno alla volta:

- **OK stimato**: pesi, cache e buffer stimati rientrano nella memoria libera con margine.
- **Offload previsto/necessario**: parte dei layer resta in RAM, oppure occorre ridurre i layer GPU. Se la configurazione attuale rischia OOM, viene scritto esplicitamente.
- **Rischio OOM**: la memoria stimata non entra nella configurazione corrente e la RAM libera non offre spazio sufficiente.
- **Non determinabile**: informazioni hardware insufficienti.

La stima cambia con modello, contesto, layer, risoluzione e numero di riferimenti allegati (almeno uno per una previsione vision). “Applica suggerimento” modifica il setup da salvare. La memoria è aggiornata durante l'apertura delle impostazioni, con cache di circa 10 secondi. Sono stime euristiche: kernel, driver, template, dimensioni reali delle immagini e memoria occupata successivamente possono cambiare il risultato. Il motore continua a riportare gli errori OOM effettivi nel lavoro.

## Chat e canvas

Puoi creare, cercare per titolo, rinominare, fissare in evidenza, archiviare, ripristinare ed eliminare conversazioni; organizzarle in raccolte e spostarle tra raccolte. Eliminare una raccolta conserva le chat. Messaggi, impostazioni, stato dei lavori e canvas sono persistiti in SQLite. Gli allegati sono file locali; quelli condivisi vengono conservati anche dopo la cancellazione di una chat.

**Canvas spento:** la risposta e le immagini appaiono nella chat.

**Canvas acceso al momento dell'invio:** il motore scrive l'artefatto nel pannello laterale, con aggiornamenti durante la generazione; nel corpo chat resta un breve messaggio standard di accompagnamento scritto dall’app, così anche un modello piccolo non può duplicare l’artefatto nel corpo. La destinazione viene salvata nella richiesta e non cambia se chiudi il pannello mentre il lavoro è in corso. Puoi chiedere modifiche all'artefatto esistente, editarne il Markdown e salvare. Le risposte completate conservano anche la versione del proprio artefatto; il pulsante «Apri canvas» permette di riportarla nel pannello.

Il canvas esporta **Markdown, PNG completo, PDF e Word (.docx)**. Il PDF conserva testo selezionabile e SVG vettoriali; i grafici canvas sono inclusi come immagini ad alta risoluzione. Il Word mantiene paragrafi, elenchi, tabelle e codice modificabili; formule, diagrammi e immagini vengono inseriti come immagini. Il formato legacy `.doc` non è previsto. L'originale di un'immagine generata è scaricabile senza convertirla in un documento.

## Rendering

- Markdown con titoli, tabelle, citazioni ed elenchi.
- Evidenziazione sintattica locale e copia dei blocchi di codice.
- LaTeX con `$...$` e `$$...$$`, tramite KaTeX.
- Diagrammi in blocchi `mermaid`, esportabili in SVG.
- Grafici in blocchi `chart`, costruiti dai numeri, con accesso ai dati e download PNG. Le serie non vengono interpolate o trasformate arbitrariamente.

Esempio:

````markdown
```chart
{"type":"line","title":"Crescita quadratica","xLabel":"x","yLabel":"x²","labels":["0","1","2","3"],"datasets":[{"label":"x²","data":[0,1,4,9]}]}
```
````

Sono supportati `line`, `bar`, `scatter`, `pie` e `doughnut`. Per `scatter` i dati sono coppie `{ "x": 1, "y": 2 }`. JSON invalido, valori non finiti e serie incongruenti vengono segnalati, senza inventare i dati mancanti. Per un riferimento fotografico il modello riceve l'istruzione di distinguere numeri leggibili, stime e parti illeggibili: la precisione dell'estrazione resta dipendente dal modello vision e dalla qualità dell'immagine.

## Hardware

| Scelta | Backend | Comportamento iniziale |
|---|---|---|
| Solo CPU | CPU | Nessun layer su GPU; immagini 512×512 |
| GPU 4–8 GB | Vulkan oppure CUDA NVIDIA | Contesto moderato, offload parziale LLM, immagini 512×512 |
| GPU 12–24 GB | Vulkan oppure CUDA NVIDIA | Contesto più ampio, più layer su GPU, immagini 768×768 |

Vulkan copre NVIDIA, AMD e Intel con driver compatibili. CUDA è per NVIDIA; la release dei motori fissa il proprio runtime CUDA. I profili sono modificabili. Il setup rileva CPU, RAM e GPU e stima il rischio di memoria per i modelli selezionati, usando anche la memoria attualmente libera; non garantisce un consumo massimo. Memoria occupata da altre applicazioni, modello, risoluzione e numero di riferimenti possono richiedere CPU, meno layer GPU o dimensioni inferiori.

Le immagini usano batch singolo, VAE a tasselli e, su GPU, offload delle parti supportate sulla RAM. FLUX.2 klein e quattro riferimenti richiedono più RAM e tempo dei modelli di base. La CPU permette di lavorare senza VRAM, con prestazioni inferiori.

## Catalogo iniziale

| Modello | Ruolo | Riferimenti |
|---|---|---:|
| Qwen3 0.6B Q4 | Chat e router leggeri | Testo |
| Qwen3 4B Q4 | Chat, codice, router | Testo |
| SmolVLM 500M Q8 | Vision essenziale, soprattutto inglese | 1 |
| Qwen2.5-VL 3B Q4 | Vision, OCR, grafici | Fino a 4 |
| Stable Diffusion 1.5 | Creazione e img2img | 1 |
| FLUX.2 klein 4B Q4 | Creazione e modifica semantica | Fino a 4 |

FLUX include encoder Qwen3 4B e VAE. Vision include il proiettore multimodale. Il catalogo fissa revisioni, dimensioni e hash dei componenti; non scarica codice Python dei repository dei modelli. Le licenze dei pesi sono indicate nel catalogo e restano quelle dei rispettivi autori. `scripts/lock_catalog.py` rigenera i manifest verificando i metadati ufficiali: è uno strumento per chi mantiene l'app, non parte dell'avvio.

I limiti degli allegati sono quattro immagini, 12 MB ciascuna e 8192 px per lato. La UI accetta PNG, JPEG e WebP; converte WebP in PNG. Se il modello scelto accetta meno riferimenti, il lavoro viene fermato con una spiegazione: nessun riferimento viene scartato silenziosamente.

## Dati, protezioni e recupero

- `data/chat.sqlite`: chat, raccolte, messaggi, lavori, impostazioni e canvas.
- `data/uploads/`, `data/outputs/`: allegati e risultati originali.
- `data/exports/`: PDF creati e documenti di stampa intermedi.
- `models/files/`: componenti condivisi, con identificazione dal checksum.
- `runtime/`: Python e motori CPU/Vulkan/CUDA isolati dall'ambiente di sistema.
- `data/logs/`: registri dei lavori; `data/server.log`: avvio dell'app.

Il servizio ascolta solo su `127.0.0.1`. Host e Origin sono verificati, le modifiche richiedono il token di sessione e il server LLM privato usa una propria chiave. La UI non esegue HTML o JavaScript generato dal modello. I download vengono scritti in `.part` e pubblicati solo dopo la verifica completa. Gli archivi con percorsi esterni o symlink sono rifiutati. Dopo un arresto inatteso le risposte incomplete sono marcate come interrotte.

Per un backup completo arresta H3-Chat e copia `data/`. Puoi escludere `data/window-profile/` e i profili temporanei degli export per ridurre lo spazio. Per liberare gli allegati orfani occorre una pulizia manuale; non sono eliminati automaticamente per evitare di rimuovere file riutilizzati.

## Sviluppo e verifica

```powershell
npm ci
npm run build
python -m unittest discover -s tests -v
npm test
python app.py
```

Il backend usa la sola libreria standard Python. Node serve per compilare gli asset; tutto ciò che serve all'interfaccia viene incluso localmente. I test del browser sono in `tests/browser-smoke.mjs`; `H3_PLAYWRIGHT` può indicare il modulo Playwright e `H3_TEST_URL` l'istanza di prova. Non puntare i test automatici a una copia con conversazioni personali.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install.ps1
python scripts/install_cpu.py
python scripts/package.py
```

Per aggiornare una vecchia installazione, arrestala con `Ferma-H3-Chat.bat`, fai un backup di `data/`, quindi estrai i file della nuova release nella stessa cartella. Le release non contengono `data/` né pesi dei modelli.

Il packaging include una lista esplicita di file, esclude chat, modelli, cache e registri personali, produce uno ZIP Windows e il suo SHA-256. Il workflow GitHub costruisce l'artefatto; su un tag `v*` prepara una **release in bozza** per la revisione del proprietario del repository. Nessun repository remoto viene creato automaticamente dall'app.

## Stato della versione 0.2

Chat CPU, streaming, canvas separato, gestione conversazioni, rendering e API sono implementati e collaudati. Le integrazioni immagini sono basate sui parametri verificati dei motori ufficiali. Il collaudo di questa versione non equivale a una certificazione di tutte le combinazioni di GPU, driver e modelli: in particolare CUDA/Vulkan e FLUX multi-riferimento richiedono ancora una prova di inferenza sulle rispettive configurazioni hardware. Video, audio, esecuzione del codice generato, ricerca web, importazione PDF/Word in ingresso e plugin non sono inclusi.

Font e layout derivano dai riferimenti locali H3-Music e H3-Comics. Motori: [llama.cpp](https://github.com/ggml-org/llama.cpp), [stable-diffusion.cpp](https://github.com/leejet/stable-diffusion.cpp). Riferimenti: [multimodalità llama.cpp](https://github.com/ggml-org/llama.cpp/blob/master/docs/multimodal.md), [FLUX.2 nel motore immagini](https://github.com/leejet/stable-diffusion.cpp/blob/master/docs/flux2.md), [FLUX.2 ufficiale](https://github.com/black-forest-labs/flux2), [Python integrato](https://www.python.org/downloads/release/python-31315/).

Implementazione thinking verificata sulla [API llama.cpp b10809](https://github.com/ggml-org/llama.cpp/blob/b10809/tools/server/README.md); rilevamento memoria tramite [DXGI](https://learn.microsoft.com/en-us/windows/win32/api/dxgi/ns-dxgi-dxgi_adapter_desc) e [GlobalMemoryStatusEx](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-globalmemorystatusex).
