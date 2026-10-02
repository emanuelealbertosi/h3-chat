# H3-Chat

Chat multimodale locale per Windows, con lo stile avorio e verde petrolio delle app H3. Una sola conversazione per testo, codice, immagini, canzoni, video, formule, grafici e diagrammi. I motori locali sono gestiti dall'app; non servono Ollama, LM Studio o ComfyUI. Gli LLM locali non richiedono chiavi API o abbonamenti; puoi scegliere anche provider LLM tramite API e server esterni per immagini, musica e video. Progetti con RAG, ricerca web e animazioni Manim restano nella stessa chat.

## Installazione

**Pacchetto Windows:** scarica [H3-Chat-0.13.4-windows-x64.zip](https://github.com/emanuelealbertosi/h3-chat/releases/download/v0.13.4/H3-Chat-0.13.4-windows-x64.zip) dalla [release v0.13.4](https://github.com/emanuelealbertosi/h3-chat/releases/tag/v0.13.4), estrailo in una cartella scrivibile e apri `H3-Chat.exe`. Il pacchetto include Python, i motori CPU e tutte le librerie dell'interfaccia. Non occorrono privilegi di amministratore. Non avviare l'app direttamente dentro lo ZIP.

Se il salvataggio delle impostazioni fallisce, il messaggio completo resta visibile dentro la finestra, accanto a **Salva impostazioni**. I valori inseriti restano disponibili per correggere l’errore e riprovare.

**Primo avvio:** apri **Impostazioni → Setup**, scegli hardware e modelli. Il catalogo scarica i pesi e tutti i componenti richiesti, controllando dimensione e SHA-256. I backend GPU si installano dallo stesso setup. Dopo i download, inferenza, interfaccia e documenti funzionano offline.

**Da GitHub, come H3-Music:** su Windows x64 esegui `git clone https://github.com/emanuelealbertosi/h3-chat.git`, entra nella cartella e apri **`install.bat`**. L'installatore prepara Python privato, estrae interfaccia e launcher precompilati, scarica i motori CPU chat/immagini/musica dalle revisioni fissate e verifica gli SHA-256. Non richiede Python di sistema, Node.js, Visual Studio o compilatori. Le librerie Microsoft necessarie ai motori vengono incluse accanto ai motori, senza installazioni di sistema. Poi usa **`start.bat`** e **`stop.bat`**; restano disponibili anche i nomi italiani Installa/Avvia/Ferma. Modelli e GPU si scelgono dal Setup: i pesi non vengono copiati da un altro PC e non vengono scaricati automaticamente dall'installatore.

L'installazione è ripetibile: conserva chat, preferenze, percorsi dei modelli e motori GPU già presenti; i motori verificati vengono riutilizzati e i download dei motori interrotti riprendono dal file parziale. Per aggiornare: termina i lavori, esegui `stop.bat`, `git pull`, `install.bat`. La connessione serve per i componenti mancanti e i modelli; in seguito l'app funziona offline. Un portatile Windows x64 senza GPU dedicata può usare il profilo **Solo CPU**, con tempi maggiori e RAM sufficiente ai modelli scelti.

Per chi modifica i sorgenti dell'interfaccia o del worker: ricostruisci il bundle seguendo [la procedura per sviluppatori](docs/build.md). L'installatore rileva un bundle non allineato ai sorgenti invece di avviare silenziosamente una vecchia interfaccia.

La finestra desktop usa Microsoft Edge in modalità app, normalmente già presente in Windows 10/11. Se Edge manca, la chat si apre nel browser predefinito; l'export PDF richiede Edge. Chiudere la finestra lascia finire il lavoro corrente. `H3-Chat.exe` e `Avvia-H3-Chat.bat` lasciano aperta una console con i log in tempo reale: avvio, errori delle operazioni e fasi di generazione. Chiudere la console (o Ctrl+C) chiude soltanto la vista dei log. `Ferma-H3-Chat.bat` arresta il servizio e i processi di inferenza posseduti dall'app. I log restano in `data/server.log`, con i dettagli dei motori in `data/logs/`.

## Provider LLM tramite API

In **Setup → LLM tramite API** collega DeepSeek, OpenRouter o un servizio Chat Completions compatibile: indirizzo base, chiave e ID modello. Puoi caricare l’elenco modelli, provare la connessione, salvare più collegamenti e premere **Usa in chat**. Chat, router e Assistant usano il provider scelto; immagini, musica e video possono usare motori standalone o server esterni. La trascrizione resta sul PC. Nessun peso LLM occupa RAM/VRAM sul PC.

Le chiavi sono protette con Windows DPAPI e non vengono mostrate o registrate nelle chat. La conversazione, gli estratti dei documenti, le trascrizioni e le immagini fornite a Vision vengono inviati al servizio selezionato. Vision/thinking/JSON si configurano per collegamento; le tariffe e il limite effettivo di contesto dipendono dal provider. In chat compare **API**, anche per Vision. [Configurazione e limiti](docs/api-providers.md).

## Progetti, fonti e animazioni

Crea un **Progetto**, collega PDF/Word/testi o cartelle e usa **RAG** per recuperare estratti nella chat. Le citazioni aprono il pannello **Fonti e file**, con documento, pagina/righe e testo evidenziato. La ricerca web funziona anche senza progetto; gli snapshot delle fonti web possono essere salvati e indicizzati nel progetto. Ricerca per parole inclusa, ricerca semantica opzionale con un GGUF embedding (EmbeddingGemma scaricabile dall’admin).

**Strumenti → Interprete numerico** esegue calcoli e dati dei grafici con sintassi Python limitata. Installa **Manim** dal Setup e chiedi «Ricava dal PDF allegato un’animazione Manim»: lo stesso LLM prepara scene validate con testi, formule, forme, frecce e grafici di funzioni. MP4 riproducibile e sorgente JSON scaricabile in chat o nel canvas. La prima versione usa storyboard dichiarativi, non tutta l’API Python Manim. [Uso e limiti](docs/projects-and-animations.md).

In admin puoi scegliere **CPU/GPU per funzione** e collegare **server esterni LLM, immagini, musica e video**. Per musica/video remoti è previsto il protocollo H3; immagini supportano anche Forge/A1111 e Images API compatibili con risposte base64. Il video MiniMax H3 resta GPU; Vision/mmproj chat resta CPU. Immagini e musica sulla CPU mostrano un avviso sui tempi. [Configurazione dei server e dispositivi](docs/external-servers.md).

## Un unico prompt

- «Scrivi una funzione Python…» → risposta con codice evidenziato.
- «Crea un'illustrazione botanica…» → motore di generazione immagini.
- «Combina queste quattro foto in una scena…» → motore di modifica, con i riferimenti numerati nell'ordine degli allegati.
- «Leggi questo grafico e ricostruiscilo…» → modello vision, dati e renderer numerico.
- «Spiegami questa formula…» → testo e LaTeX.
- «Crea una canzone rock…» oppure il pulsante **Music** → motore musicale YuE2.
- «Crea un video…», «Anima questa immagine» oppure **Video** → MiniMax H3, con default 15 secondi / 0,7 MP.
- «Ricava dal PDF un’animazione Manim» → storyboard validato e MP4.
- «Usa l’interprete per calcolare e disegnare…» → dati calcolati e grafico.

La chat resta unica. Nel composer puoi lasciare Immagini su Automatico oppure selezionare esplicitamente il modello immagini. Le richieste esplicite più comuni sono riconosciute direttamente; quelle ambigue sono classificate dal modello chat con uno schema JSON vincolato. I modelli piccoli possono interpretare male richieste complesse: per codice, routing e analisi densa scegli un modello più capace dal setup.

Le selezioni principali nelle impostazioni sono **chat/router/vision**, **creazione immagini** e **modifica immagini**. Un solo modello è assegnato a ciascun ruolo. La modalità A richiesta conserva il modello corrente e lo scarica prima di caricarne uno diverso; Residenti conserva i modelli scelti. Le due modalità sono selezionabili dal Setup. La coda è globale e seriale, con interruzione del lavoro e registrazione degli errori. Con backend GPU, diffusore, encoder e VAE immagini usano la GPU anche in **A richiesta**: questa opzione scarica un modello quando si passa a un altro, senza spostarne il calcolo sulla CPU. Soltanto il mmproj della chat resta sulla CPU. Se la VRAM non basta, il setup segnala rischio OOM; scegli pesi o risoluzioni inferiori oppure seleziona esplicitamente CPU. La decodifica VAE viene mostrata come fase separata: i suoi blocchi non sono ulteriori step di generazione.

## Canzoni e musica · YuE2

Premi **Music** nella chat oppure chiedi «Crea una canzone», «Genera musica» o «Componi un brano». Il router riconosce la richiesta audio; parlare di musica o chiedere solo un testo resta una risposta testuale. Il routing automatico musicale può essere disattivato nelle impostazioni; il pulsante Music continua a funzionare.

**Assistant On** prepara stile e testo con lo stesso LLM della chat, riutilizzandolo se già caricato. **Assistant Off** usa i tuoi campi titolo, stile, testo e, facoltativamente, spartito ABC: non richiede un LLM installato per richieste musicali esplicite. Puoi scrivere i campi anche nel messaggio dopo `Titolo:`, `Stile:` e `Testo:`. Per musica senza parole attiva **Strumentale**. L’app ricorda Music, Assistant e campi per ciascuna chat.

In **Impostazioni → Musica · YuE2**, scegli i GGUF principale e VAE con **Sfoglia e collega YuE2**. Il tokenizer e le tre configurazioni sono rilevati nella sottocartella `sidecars` accanto ai pesi principali, con i nomi originali YuE2. Il VAE può trovarsi altrove. I file restano nei percorsi originali. In alternativa **Scarica YuE2 Q8** installa modello e tutti i componenti dal catalogo verificato.

Il modello iniziale è **YuE2-3B Q8**, con i preset di H3-Music: **Melodia e accordi, 32 passi, CFG 1, seed 831001**, 8 thread CPU. **Avanzate** nelle preferenze modifica i parametri per modello; **Avanzate** in chat mostra i parametri effettivi. I limiti dei token non indicano una durata esatta: se vengono raggiunti, la chat avverte che la fine può essere troncata.

Il risultato ha un player con avanzamento e download **WAV stereo 48 kHz**. Con canvas attivo, player e testo sono nel canvas e in chat resta il messaggio di accompagnamento. Il testo del canvas può essere esportato nei formati già disponibili; il WAV si scarica separatamente. La chat conserva la composizione per revisioni successive, ma non ascolta né analizza l’audio generato.

Il motore musicale CPU è incluso nel pacchetto Windows; il motore NVIDIA CUDA si installa dal Setup e poi funziona offline. Non occorre H3-Music, un server esterno o il CUDA Toolkit. AMD/Intel possono usare CPU per YuE2; questo motore non supporta Vulkan. **A richiesta** libera l’LLM prima della musica e YuE2 prima di tornare alla chat. **Residenti** conserva i processi; YuE2 alterna comunque internamente pianificazione, sintesi e decodifica per contenere la VRAM. Le stime RAM/VRAM sono prudenziali: su poca VRAM si può scegliere CPU, senza promessa di offload GPU parziale.

Il canto italiano è sperimentale. I pesi YuE2 sono soggetti a **CC BY-NC 4.0**; non sono inclusi nell’archivio dell’app. Dettagli, build e provenienza: [motore musicale](docs/music-engine.md).

## Video · MiniMax H3

Il video mantiene il formato del primo fotogramma guida, senza deformare le immagini. Con soli riferimenti puoi indicare un formato diverso nel prompt, per esempio «solo reference, formato 16:9». Senza immagini vale il formato richiesto o il preset. Il motore aggiunge il minimo margine per la propria griglia e lo rimuove dal file finale.

In **Setup → Video**, il pulsante **Installa acceleratore video** aggiunge SageAttention e i suoi componenti al runtime privato. Il preset **Auto** lo usa quando disponibile; nelle impostazioni avanzate puoi scegliere Sage o PyTorch e la suddivisione dell’attenzione. L’offload completa e libera encoder e VAE prima di leggere il diffusore, poi libera il diffusore prima della decodifica. Tutto il calcolo video resta sulla GPU.

Nella stessa chat premi **Video** oppure chiedi «Crea un video», «Genera un filmato» o «Anima questa immagine». Il risultato è un MP4 con audio, player e download; con canvas attivo appare nel canvas. In **Setup → Video → Sfoglia e collega** scegli diffusore H3 standard FL2VA/REF2VA, encoder Qwen3-VL per H3, VAE video e VAE audio, tutti safetensors e nelle loro cartelle originali. Il motore privato si installa dallo stesso pannello, è condiviso con Ming/Qwen e poi funziona offline. Richiede NVIDIA CUDA; PDD/Turbo e GGUF non sono supportati.

Modello predefinito: **Hybrid**, selezionabile e sostituibile dall’admin tramite i file originali. Default per modello: **15 secondi, 0,7 MP, 16:9 (1152×640), 24 fps, 12 step, CFG 1, Res Multistep/Simple**. In **Avanzate** puoi cambiare durata, risoluzione, formato, passi, sampler, scheduler, seed e shift. L’offload è attivo per contenere la VRAM; il calcolo resta sulla GPU. Encoder e VAE vengono liberati dopo il condizionamento; il diffusore dopo il campionamento, prima di ricaricare i VAE necessari alla decodifica. Questo evita il crash nativo osservato su Windows nel trasferimento GPU→CPU dell’encoder quantizzato NVFP4/AWQ. Disattivare l’offload richiede memoria sufficiente per tutti i componenti. **A richiesta** libera l’altro motore prima del video; **Residenti** conserva il processo e rispetta comunque l’offload del preset.

Allega fino a **9 immagini e 3 audio** (WAV, MP3, FLAC, OGG). Scrivi, per esempio: «Immagine 1 come frame iniziale, immagine 2 a 7 secondi, immagine 3 come riferimento del personaggio. Usa audio 1 con lip-sync». **Assistant On** prepara istruzioni inglesi, ruoli e tempi usando lo stesso LLM chat; dialoghi e parole restano nella lingua richiesta. Vision On usa il mmproj chat sulla CPU quando disponibile. Assistant non trascrive audio; il motore video riceve la traccia originale. **Assistant Off** passa il prompt direttamente e riconosce indicazioni esplicite come `immagine 2 a 7 secondi`; [guida e limiti](docs/video-engine.md).

Il lip-sync usa l’audio per condizionare la generazione con denoise audio zero e almeno 8 passi standard, poi conserva la traccia sorgente nel MP4. La sincronizzazione visiva dipende dal modello. Una traccia da conservare deve coprire la durata scelta; i brevi riferimenti di voce o stile non devono coprire tutto il video. Il limite di output dell’Assistant si salva per ciascun LLM. **Avanzate in chat** mostra istruzioni, ruoli e parametri effettivi del video.

## PDF, Word, web e trascrizione

Allega **PDF o Word .docx** alla chat (fino a tre documenti, 25 MB ciascuno; PDF fino a 300 pagine). L’app estrae testo e tabelle localmente e conserva riferimenti a pagine/blocchi. Per documenti lunghi passa all’LLM estratti pertinenti e lo indica nella risposta. I file restano disponibili per domande successive. Per scansioni o figure PDF abilita Vision e indica le pagine: vengono fornite fino al limite di immagini del modello, massimo quattro pagine per lettura. Le altre pagine non vengono dichiarate lette. Word legacy `.doc`, macro e PDF protetti da password non sono supportati.

**Web** forza una ricerca per il messaggio; “cerca sul web…” viene riconosciuto automaticamente se abilitato nelle preferenze. Default DuckDuckGo con fallback Bing; Bing e una propria istanza SearXNG sono selezionabili. L’app legge le fonti pubbliche e aggiunge link reali alla risposta o al canvas. Se una pagina blocca l’accesso, la fonte è indicata come solo estratto. Se non recupera risultati pertinenti, mostra un errore: non simula una ricerca. Solo il messaggio di ricerca viene inviato al provider, non i file allegati.

Gli **audio allegati a una richiesta chat** vengono trascritti localmente; puoi chiedere un riassunto o fare domande sul parlato usando il tuo LLM. **Trascrivi** oppure “trascrivi questo audio” restituisce la trascrizione anche senza LLM, con download **TXT/SRT**. Il pulsante Canvas porta testo e download nel pannello laterale. Gli audio usati come riferimenti Video restano originali e non attivano automaticamente la trascrizione.

In **Setup → Documenti, ricerca e trascrizione**, installa il motore opzionale e scarica **Whisper Small multilingue** (default) oppure **Tiny**. Puoi scegliere una cartella Faster Whisper/CTranslate2 già presente altrove con `model.bin`, `config.json` e `tokenizer.json`; nessun peso viene copiato. Imposta lingua, thread e beam. Inferenza **CPU INT8**, processo liberato dopo la richiesta, nessuna VRAM aggiuntiva; massimo tre audio, 64 MB e 30 minuti ciascuno. Non è un motore di analisi musicale, rumori, emozioni o identità vocale. I risultati possono contenere errori.

I componenti PDF/Word sono inclusi nello ZIP Windows e preparati da `install.bat` nei clone; il runtime audio e i pesi si installano dal Setup con SHA-256 e revisioni fissate. Dopo l’installazione, documenti e trascrizione funzionano offline. [Guida e limiti](docs/chat-tools.md).

## Vision e modelli locali

Il composer offre **Vision On / Off** (On di default) e indica **Vision · CPU**, **Vision disattivata** oppure **Non vision**, con un avviso se manca il proiettore. Il nome commerciale del modello non basta: l'app verifica la presenza del `mmproj`. Nei modelli del catalogo usa esclusivamente il componente associato; non prende proiettori di altri modelli dalla cache condivisa. Se il proiettore viene rimosso da un modello già installato, i pesi verificati restano utilizzabili per il testo e il catalogo permette di completare di nuovo il download.

Per usare un GGUF già scaricato, apri **Catalogo modelli → Collega un modello → Chat / vision** e scegli il file con **Sfoglia** oppure incolla il suo percorso completo. Non serve copiarlo in H3-Chat. In modalità mmproj Automatico l’app cerca il proiettore nella stessa cartella: se ne trova uno lo usa, se ne trova più di uno segnala l’ambiguità e puoi sceglierlo manualmente. Le vecchie cartelle `models/local/NomeModello/` continuano a essere rilevate. I metadati GGUF vengono letti senza eseguire codice; il proiettore presente nella stessa cartella viene passato automaticamente al motore. Se ci sono più proiettori non viene scelto arbitrariamente. La presenza del file non certifica l'abbinamento: un proiettore incompatibile viene rifiutato dal motore. Il GGUF deve essere supportato dalla versione integrata di llama.cpp. I file locali non sono scaricati né verificati contro un hash del catalogo.

Il proiettore vision usa sempre la CPU, anche con modelli Residenti. Vision Off evita di caricarlo e libera la sua RAM; i token delle immagini continuano a occupare contesto LLM quando Vision è On.

Senza vision, la chat testuale continua a funzionare e le risposte conservano l'indicazione. Una richiesta di lettura delle immagini viene fermata con un messaggio esplicito; creazione e modifica artistica continuano a usare il proprio motore immagini.

## Modelli già scaricati in altre cartelle

**Impostazioni → Catalogo modelli → Collega un modello** registra soltanto i percorsi assoluti dei file in `data/chat.sqlite`. Puoi usare altre cartelle, unità locali o percorsi UNC accessibili al tuo utente Windows. Sfoglia mostra le unità e le cartelle; puoi anche incollare un percorso. La navigazione è esplicita, una cartella alla volta: nessuna scansione automatica dell’intero disco.

- **Chat / vision:** GGUF, anche suddiviso in più parti (seleziona la prima `00001`). Il mmproj è automatico nella stessa cartella, selezionabile manualmente oppure disattivabile. Se manca, il modello resta utilizzabile per il testo con avviso Non vision. La presenza di un proiettore non certifica la compatibilità: il motore verifica l’abbinamento al caricamento.
- **Stable Diffusion / SDXL:** checkpoint completo GGUF o safetensors, con eventuale VAE esterno.
- **FLUX.2 klein:** diffusore, encoder LLM e VAE. Puoi selezionare ogni componente nella sua cartella originale. Passi e CFG sono configurabili, con valori iniziali per i modelli distillati.
- **Qwen Image Edit:** diffusore, encoder testo, encoder vision e VAE; selezione esplicita dei componenti e dei parametri di campionamento.

I file riconoscibili nella stessa cartella vengono proposti come componenti; controlla che appartengano al modello scelto. Questa funzione collega file compatibili con i motori inclusi: non converte checkpoint PyTorch `.ckpt`/`.bin`, directory Diffusers o architetture non supportate. Non viene eseguito codice Python proveniente dalle cartelle dei modelli. I file locali sono controllati per formato e disponibilità, senza copiarli né calcolare ogni volta un hash completo dei pesi.

Dopo il collegamento scegli il modello nel Setup per chat, creazione o editing. Lo stesso modello immagini può occupare entrambi i menu e condivide un solo caricamento. Vision, Think, stime RAM/VRAM, modalità Residenti/A richiesta e cache si applicano anche ai collegamenti esterni.

**Modifica collegamento** corregge i percorsi se sposti i file o cambi unità. Se un file non è più disponibile, il modello resta nel catalogo con un avviso. **Scollega** elimina soltanto il riferimento dall’app: non cancella, sposta o sovrascrive i file originali. Durante un lavoro i collegamenti non possono essere sostituiti o rimossi; interrompi o attendi il lavoro. Usa Libera memoria prima di spostare manualmente pesi in uso. Il backup di `data/` conserva i collegamenti, ma non include i file esterni: su un altro computer occorre correggere i percorsi.

## Immagini, Anima e LoRA

In **Preferenze → Impostazioni immagini** trovi i valori predefiniti per modello. Attiva **Avanzate** per modificarli; disattivarlo nasconde i controlli mantenendo i valori salvati. Il secondo flag **Avanzate nella chat** mostra i parametri effettivi delle immagini.

**Anima Turbo 1.1 Q4** è scaricabile con encoder Qwen3-0.6B Base e VAE Qwen Image. Puoi anche collegare Anima Base/Aesthetic o Turbo dalle cartelle originali. In **Preferenze → Cartelle LoRA** scegli una o più cartelle; in chat, **LoRA** permette di selezionare fino a otto adapter con peso e modello destinatario. I file restano dove si trovano. [Guida a preset, parametri e LoRA](docs/images-and-loras.md).

## Ming, Qwen Image 2.1 e Assistant

Nel Setup trovi sezioni dedicate a **Ming Image 0.1 Design** e **Qwen Image 2.1**.
Collega diffusore, encoder e VAE safetensors con **Sfoglia e collega**, senza copiare
i pesi. Ming: preset 1024×1024 / 12 step / CFG 1 / Euler-Simple; Qwen 2.1:
1024×1024 / 25 step / CFG 1 / Euler-Simple. Entrambi creano e modificano immagini,
con fino a quattro riferimenti. I parametri restano personalizzabili per modello.

**Ming automatico per grafici** instrada le richieste di creazione di grafici, grafi,
schemi e diagrammi al Ming scelto. Spiegazioni e richieste esplicite di Mermaid,
Chart, SVG, codice o grafici esatti continuano a usare il renderer strutturato.
Il menu Immagini in chat permette una scelta esplicita che prevale sul routing.
Qwen 2.1 può essere impostato come predefinito per crea e modifica.

**Assistant On / Off**, attivo di default in chat, prepara le istruzioni per tutti
i modelli immagini usando **lo stesso LLM della chat**, riutilizzato se già caricato.
Le istruzioni seguono il modello effettivamente selezionato: **Anima e SDXL/Stable
Diffusion ricevono tag in inglese separati da virgole**, Ming e Qwen Image ricevono
istruzioni descrittive, con indicazioni precise per grafici e diagrammi. FLUX usa
istruzioni descrittive. Il testo da inserire visibilmente nelle immagini conserva
la lingua richiesta. Con Off il prompt originale passa direttamente e le richieste
immagini esplicite non richiedono un LLM installato. Vision On consente anche ad Assistant di
leggere i riferimenti tramite il proiettore sulla CPU; Vision Off lascia comunque
passare i riferimenti al modello immagini per l'editing. Scelte, prompt effettivo,
parametri e destinazione canvas sono conservati con ogni lavoro.

Il motore aggiuntivo si installa una sola volta dal Setup (circa **2,1 GB** di
download, circa 4 GB estratti). È privato all'app: non richiede ComfyUI o LM Studio
installati o avviati. Usa una libreria ComfyUI incorporata, con Python e PyTorch
isolati. NVIDIA CUDA oppure CPU; Vulkan resta per gli altri motori.
[Dettagli, sorgenti e licenze del motore](docs/vision-engine.md).

## Preset dei singoli modelli

Nel Setup scegli i modelli **predefiniti**. In **Preferenze** scegli invece il **Modello da configurare**: modificarne il preset non cambia quello predefinito. Dal Catalogo puoi aprire direttamente **Parametri del modello**. Salva per conservare i valori.

- **LLM:** contesto, max token, temperatura, thinking, layer GPU, MTP e limiti di output dell’Assistant immagini/musica/video vengono ricordati per ciascun modello. Se cambi LLM ritrovi i suoi valori. La configurazione già salvata viene conservata come preset del LLM attuale.
- **Immagini:** risoluzione, step, CFG, sampler, scheduler, seed, negative prompt e intensità di editing appartengono al modello selezionato. Con **Avanzate** li modifichi; vengono usati tanto dalla scelta esplicita in chat quanto dal routing automatico.
- **Musica:** ogni modello conserva il proprio preset di generazione.

Backend, profilo hardware, thread, politica di memoria e istruzioni personali rimangono preferenze generali. Ogni lavoro conserva i valori presenti al momento dell’invio.

## MTP e max token

In **Preferenze → Parametri dei modelli chat → Contesto LLM** puoi impostare 64k (65.536 token), 128k, 256k e altri valori manuali: non c’è più il precedente tetto di 32.768 token. L’app legge il contesto dichiarato dal GGUF del modello selezionato e lo mostra accanto al campo. Se lo superi compare un avviso: il supporto dell’estensione dipende dal modello e dal motore, non è garantito dall’app. Se il dato manca, l’app lo indica senza inventare un limite. La stima di memoria include la KV cache per l’intero contesto scelto; salvare un contesto maggiore non garantisce che entri nella RAM/VRAM disponibile. Il valore viene passato al motore al prossimo caricamento.

Il **contesto totale** comprende istruzioni, cronologia, token delle immagini e risposta. **Max token di risposta** limita solo l’output della chat; **Max token Assistant** limita le istruzioni prodotte per immagini, musica o video e non modifica il contesto LLM.

In chat, accanto a Think, il pulsante **MTP · Max token** mostra lo stato e il limite di risposta e apre le **Preferenze**. **Max token di risposta** era già disponibile e mantiene il valore salvato: 64–8192 token, fino a metà del contesto, comprendendo il thinking e gli artefatti nel canvas.

Puoi attivare **MTP** e scegliere **1–8 token da anticipare** (3 iniziali) per i GGUF completi che incorporano moduli NextN supportati dal motore. Il rilevamento legge metadati e tensori, anche tra più shard; un nome contenente “MTP” non basta. Sui modelli incompatibili compare **MTP N/D**, l'opzione è disabilitata e la chat continua normalmente. Il motore verifica l'attivazione effettiva dopo il caricamento.

MTP usa pesi condivisi e un contesto aggiuntivo, incluso nelle stime RAM/VRAM. Cambiare MTP ricarica il modello; max token e Think si applicano senza ricaricarlo. [Dettagli, limiti e fonti](docs/mtp.md). [Verifiche della versione 0.5](docs/validation-v0.5.md).

## Thinking nella chat

Il menu **Think** offre **Off, Low, Med, High e XHigh**. È abilitato solo se i metadati/template del modello indicano un thinking compatibile (oppure per i modelli del catalogo con supporto noto). Qwen3 lo supporta; SmolVLM e Qwen2.5-VL del catalogo non lo espongono.

I livelli riservano rispettivamente 0%, 12,5%, 25%, 50% e 75% del limite di risposta al ragionamento, lasciando spazio al testo finale. Con 1024 token: 0, 128, 256, 512 e 768. Il valore è un budget massimo, non un numero di token obbligatorio e non una garanzia di qualità. Per template con livelli nativi viene inviato anche il livello supportato; XHigh usa il livello nativo High quando il template non accetta XHigh, mantenendo il budget più ampio. Per artefatti lunghi aumenta la risposta massima e il contesto nelle Preferenze.

La scelta è salvata e fotografata in ogni richiesta, anche con canvas attivo. Il router usa sempre Think Off per evitare lavoro aggiuntivo prima di una generazione immagini. La fase thinking è indicata nello stato; la risposta e il canvas ricevono solo il contenuto finale, senza i token di ragionamento.

## Modelli residenti o a richiesta

In **Impostazioni → Setup → Modelli in memoria** scegli:

- **A richiesta** (predefinito): conserva il modello corrente fra i messaggi. Prima di usarne uno diverso, termina il processo precedente per liberare RAM/VRAM. Chat → creazione → editing → chat comporta i cambi necessari; se crea ed edit condividono lo stesso modello, il processo e i pesi vengono riutilizzati. Le richieste immagini esplicite non caricano inutilmente il router LLM; quelle ambigue possono richiederlo.
- **Residenti**: al prossimo messaggio carica tutti i modelli selezionati e già installati, poi li conserva fino al cambio di configurazione, al rilascio manuale o alla chiusura. Sulla GPU richiede tutti i layer LLM e i componenti dei modelli immagini; il mmproj resta sulla CPU; con CPU conserva tutto in RAM. I modelli non scaricati non vengono caricati automaticamente. Il numero di layer GPU nelle Preferenze vale per A richiesta.

Durante il lavoro, l’animazione nella risposta distingue **creazione immagini, modifica immagini, musica, video e scrittura nel canvas**, con fase corrente e tempo trascorso. I motori comunicano caricamento o riuso del modello e avanzamento della generazione. Per Qwen Image 2.1 con CFG 1 viene evitata l’elaborazione della condizione negativa, che non partecipa al risultato.

Il pulsante memoria sotto la chat mostra quanti modelli sono caricati e apre il setup. **Libera memoria** scarica tutti i modelli e chiude la cache quando non ci sono lavori; i file su disco e le chat restano disponibili. Un cambio di modello, backend, contesto o modalità ricarica i contesti interessati. Think, temperatura e dimensioni dell'immagine non obbligano a ricaricare i pesi. Le impostazioni cambiate durante un lavoro si applicano dopo quel lavoro; ogni richiesta conserva la propria configurazione.

La **cache file in RAM recuperabile**, facoltativa e limitabile a 0/2/4/8/16/32 GiB, conserva mapping in sola lettura dei pesi usati di recente (predefinito 2 GiB). Non duplica i pesi in un buffer Python e non blocca RAM fisica. Il limite riguarda i byte mappati, non una quantità di RAM fisica riservata: Windows può recuperarne le pagine e usa anche la propria cache disco. Quando le pagine sono ancora disponibili, il ricaricamento può evitare letture dal disco; restano necessari inizializzazione del contesto e trasferimenti alla GPU. I modelli già residenti consentono il riuso più completo; scaricare il processo LLM perde anche la sua KV cache. Con cache attiva e modalità A richiesta, il motore immagini Ming/Qwen resta inizializzato dopo aver liberato i pesi. Non conserva il modello per inferenza: evita di ripetere l’importazione di Python/PyTorch/Comfy al successivo caricamento. Usa ancora RAM per le librerie e un piccolo contesto CUDA; Cache disattivata o Libera memoria chiudono anche quel processo. Prima di un video locale in modalità A richiesta il processo immagini viene sempre chiuso: il runtime inattivo può trattenere diversi GB di RAM e memoria impegnata, che servono all’offload di H3. Tornando alle immagini viene reinizializzato. Residenti mantiene i modelli come richiesto. Il primo avvio resta completo. I log distinguono avvio, lettura dei pesi, trasferimento dei componenti e tempo di caricamento. Questa ottimizzazione riguarda il motore Ming/Qwen, non il processo llama.cpp o i motori nativi SD/Musica/Video. Prima di sostituire manualmente file di modelli, usa Libera memoria.

La stima nel setup include pesi, proiettore, encoder, KV cache, risoluzione e riferimenti. La memoria libera misurata comprende anche l'occupazione dei modelli già caricati: per confrontare configurazioni a freddo usa Libera memoria e Aggiorna. Le stime sono conservative e non garantiscono assenza di OOM.

Il motore immagini usa `native/h3-sd-worker.exe`, un processo persistente con protocollo JSON su pipe private, senza porte HTTP. Il worker carica le DLL CPU/Vulkan/CUDA già incluse nei motori, con ABI verificata su stable-diffusion.cpp `7f410a3`. Il binario è incluso nel repository e nello ZIP: l'utente non deve compilare nulla. Per ricompilarlo da sorgente servono MSVC Build Tools x64 e `powershell -File scripts/build-sd-worker.ps1`.

## Verifica preventiva della memoria

Il setup mostra CPU e thread, RAM totale/libera e GPU con VRAM totale/libera quando il driver la espone. NVIDIA usa `nvidia-smi`; su Windows DXGI rileva anche AMD/Intel, e i contatori WDDM integrano la memoria libera quando disponibili. La RAM condivisa delle GPU integrate non viene sommata alla VRAM dedicata. Più GPU o contatori mancanti producono una stima non determinabile, non un falso “OK”.

Ogni modello selezionato ha una valutazione separata. La valutazione complessiva usa il massimo in modalità A richiesta e la somma prudente dei modelli distinti in Residenti; creazione ed editing con gli stessi pesi contano una volta:

- **OK stimato**: pesi, cache e buffer stimati rientrano nella memoria libera con margine.
- **Offload previsto/necessario**: parte dei layer resta in RAM, oppure occorre ridurre i layer GPU. Se la configurazione attuale rischia OOM, viene scritto esplicitamente.
- **Rischio OOM**: la memoria stimata non entra nella configurazione corrente e la RAM libera non offre spazio sufficiente.
- **Non determinabile**: informazioni hardware insufficienti.

La stima cambia con modello, contesto, layer, risoluzione e numero di riferimenti allegati (almeno uno per una previsione vision). “Applica suggerimento” modifica il setup da salvare. La memoria è aggiornata durante l'apertura delle impostazioni, con cache di circa 10 secondi. Sono stime euristiche: kernel, driver, template, dimensioni reali delle immagini e memoria occupata successivamente possono cambiare il risultato. Il motore continua a riportare gli errori OOM effettivi nel lavoro.

## Chat e canvas

La freccia circolare accanto a **Invia** rigenera l’ultimo prompt con gli stessi allegati, modelli, parametri e scelte di quel messaggio. Sostituisce l’ultima risposta senza duplicare la richiesta e lascia intatta la bozza nel compositore. Durante un lavoro o nelle chat archiviate il pulsante è disabilitato. Con seed fisso la generazione può restituire lo stesso risultato; usa -1 per un seed casuale.

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

Il motore immagini C++ usa batch singolo e VAE a tasselli. Con backend GPU, diffusore, encoder e VAE usano la GPU; A richiesta cambia la durata di permanenza dei modelli, non il dispositivo di calcolo. Ming e Qwen 2.1 usano invece offload dinamico e spostano encoder/VAE a richiesta; il proiettore vision dell’LLM resta sempre sulla CPU. FLUX.2 klein e quattro riferimenti richiedono più RAM e tempo dei modelli di base. La CPU permette di lavorare senza VRAM, con prestazioni inferiori.

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
- `data/logs/`: registri dei lavori; `data/server.log`: avvio, operazioni, errori e fasi di generazione.

Il servizio ascolta solo su `127.0.0.1`. Con Tailscale installato e connesso, H3-Chat configura automaticamente **Tailscale Serve** per accedere all’intera app via HTTPS dagli altri dispositivi autorizzati della propria rete. L’indirizzo compare nei log di avvio e in **Impostazioni → Accesso da Tailscale**, con copia e riprova. Non vengono sovrascritti servizi esistenti: la porta HTTPS è scelta tra 8787 e 8797, riutilizzando solo il proxy privato corrispondente. Host e Origin accettano soltanto gli indirizzi locali e l’HTTPS verificato di quel proxy; le modifiche richiedono sempre il token di sessione. L’accesso riguarda anche impostazioni, modelli e file selezionabili dell’app: limita i dispositivi autorizzati con le regole della tua rete Tailscale. Senza Tailscale, H3-Chat continua a funzionare localmente.

La configurazione Serve resta salvata in Tailscale: con H3-Chat spento il motore non risponde. Non viene attivato Funnel né aperta una porta sulla LAN o sul router. MagicDNS e HTTPS devono essere disponibili nella tailnet; se manca un requisito, l’app mostra il motivo e permette di riprovare dopo averlo abilitato. [Documentazione ufficiale Tailscale Serve](https://tailscale.com/docs/features/tailscale-serve).

Il server LLM privato usa una propria chiave. La UI non esegue HTML o JavaScript generato dal modello. I download vengono scritti in `.part` e pubblicati solo dopo la verifica completa. Gli archivi con percorsi esterni o symlink sono rifiutati. Dopo un arresto inatteso le risposte incomplete sono marcate come interrotte.

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

## Stato della versione 0.6

Preset, controlli Avanzate e LoRA sono descritti nelle [verifiche della 0.6](docs/validation-v0.6.md).

I collegamenti esterni sono verificati anche con un modello vision reale caricato fuori dalla cartella dell’app, senza copie dei pesi: [Verifica 0.4](docs/validation-v0.4.md).

Chat CPU, streaming, canvas separato, gestione conversazioni, rendering e API sono implementati e collaudati. Creazione, editing e riuso dei processi immagini sono stati eseguiti su CPU con SD 1.5; i dettagli sono in [Verifica 0.3](docs/validation-v0.3.md). Il collaudo di questa versione non equivale a una certificazione di tutte le combinazioni di GPU, driver e modelli: in particolare CUDA/Vulkan e FLUX multi-riferimento richiedono ancora una prova di inferenza sulle rispettive configurazioni hardware. Video e musica sono inclusi; la versione 0.11 aggiunge ricerca web, importazione PDF/Word e trascrizione del parlato. La versione 0.13 aggiunge progetti/RAG, interprete numerico limitato, storyboard Manim e server esterni multimediali. Python generale, analisi di musica/rumori, identificazione dei parlanti e plugin non sono inclusi.

Font e layout derivano dai riferimenti locali H3-Music e H3-Comics. Motori: [llama.cpp](https://github.com/ggml-org/llama.cpp), [stable-diffusion.cpp](https://github.com/leejet/stable-diffusion.cpp). Riferimenti: [multimodalità llama.cpp](https://github.com/ggml-org/llama.cpp/blob/master/docs/multimodal.md), [FLUX.2 nel motore immagini](https://github.com/leejet/stable-diffusion.cpp/blob/master/docs/flux2.md), [FLUX.2 ufficiale](https://github.com/black-forest-labs/flux2), [Python integrato](https://www.python.org/downloads/release/python-31315/).

Implementazione thinking verificata sulla [API llama.cpp b10809](https://github.com/ggml-org/llama.cpp/blob/b10809/tools/server/README.md); rilevamento memoria tramite [DXGI](https://learn.microsoft.com/en-us/windows/win32/api/dxgi/ns-dxgi-dxgi_adapter_desc) e [GlobalMemoryStatusEx](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-globalmemorystatusex).

### Versione del motore all’avvio

L’avvio controlla tutte le istanze di questa installazione sulle porte locali dell’app. Se trova un motore precedente, lo riavvia con il codice installato quando non ci sono generazioni o download in corso. Una vecchia istanza attiva viene lasciata lavorare: termina il lavoro e riapri H3-Chat. **Ferma-H3-Chat.bat** chiude tutte le istanze della stessa installazione. Le altre installazioni non vengono toccate.

Le impostazioni richiedono uno stato aggiornato dal motore prima di aprirsi; se la versione è incompatibile viene mostrata una spiegazione, senza perdere i valori salvati.
