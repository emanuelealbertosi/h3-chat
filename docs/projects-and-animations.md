# Progetti, fonti e animazioni

## Progetti e RAG

Premi **＋ accanto a Progetti**, assegna un nome e salva. Nella sezione Documenti
premi **Scegli file…** per aprire il selettore del sistema e scegliere più file,
**Importa cartella…** per scegliere una cartella, oppure trascina file e cartelle
nel riquadro. PDF, Word `.docx`, testo e codice sono supportati. I documenti
vengono copiati nel progetto e indicizzati automaticamente; gli originali non
vengono modificati. Funziona anche dal browser di un altro dispositivo tramite
Tailscale. L'importazione mostra il progresso e riconosce i file già presenti.
I file non supportati nelle cartelle vengono ignorati.

Per usare invece i file nei loro percorsi originali, apri **Collega percorsi
originali · senza copia** e usa **Collega cartella originale…** oppure inserisci
i percorsi, quindi premi **Collega e indicizza**. Questi percorsi appartengono al
computer dove gira H3-Chat. L'indice SQLite viene salvato nella cartella dati
dell'app. Le cartelle collegate vengono ricontrollate
durante l'aggiornamento e prima delle risposte. Scollegare un documento impedisce
che la cartella lo aggiunga di nuovo; scollegare la cartella ferma il rilevamento,
ma conserva i documenti già indicizzati.

Seleziona un progetto per aprire una sua chat o crearne una. Dal menu della chat
puoi spostare anche conversazioni esistenti. Raccolte, pin e archivio continuano
a funzionare. Eliminare il progetto conserva le chat e i file originali.

**RAG** nel composer attiva/disattiva la ricerca per il messaggio. **Fonti e file →
File** permette di selezionare i documenti da usare. Le istruzioni del progetto
restano attive anche con RAG spento. La ricerca per parole funziona subito;
**Setup/Preferenze → Progetti e ricerca nei documenti** permette di scaricare
EmbeddingGemma Q8 (334 MB) o scegliere un GGUF embedding originale. I prefissi
EmbeddingGemma, E5, Nomic e generico sono selezionabili. Il default semantico è CPU;
GPU usa il motore CUDA opzionale. Le fonti restano isolate per progetto.

Ogni risposta conserva gli estratti effettivamente passati al modello. **[R1]**
apre il testo evidenziato con documento e pagina/righe. Solo riferimenti esistenti
sono cliccabili: quelli inventati vengono segnalati. Un controllo confronta alcune
citazioni letterali con gli estratti: non certifica la correttezza di tutte le
affermazioni. Gli snapshot restano consultabili anche dopo modifiche agli originali.
L'opzione **Rispondi solo dalle fonti** istruisce il modello a dichiarare le lacune;
la qualità dipende comunque dall'LLM. Il contesto può contenere solo estratti,
non necessariamente tutto il progetto. Ovis con immagini RAG attive può cercare
anche le pagine scansionate visivamente; non esegue una trascrizione OCR completa.
Gli embedding solo testo richiedono un PDF con testo OCR.

Limiti: 500 documenti per progetto, **512 MB per documento**, **3.000 pagine per
PDF**, dieci milioni di caratteri estratti e 20.000 estratti per documento.
Il caricamento trasferisce blocchi da 2 MB con percentuale visibile; gli embedding
sono preparati in piccoli gruppi e conservati temporaneamente su disco prima di
pubblicare l'indice completo. La prima indicizzazione di un libro può richiedere
tempo, soprattutto con embedding grandi su CPU. Se il file e il modello non
cambiano, le richieste successive riutilizzano l'indice.

Cartelle fino a quattro livelli, massimo 12 estratti per risposta.
Gli allegati diretti alla chat mantengono il limite separato di 25 MB e 300 pagine.
Per ricerca lessicale o embedding solo testo, prepara un PDF scansionato con OCR.
Indicizzazione fallita o file cancellati
non restituiscono vecchi contenuti. Percorsi mancanti/errori sono visibili nella
gestione del progetto.

### Ovis-Omni-Embedding-3B

In **Impostazioni → Preferenze → Progetti e ricerca nei documenti** puoi scegliere
**Ovis-Omni-Embedding-3B** come formato embedding. Installa i componenti
**Ovis / Vision**, poi usa **Scarica Ovis** (circa 11,1 GB) e **Usa Ovis scaricato**.
Se i pesi sono già presenti, scegli **Sfoglia** e indica la cartella originale:
non vengono copiati. Sono accettate sia la cartella con `config.json`, tokenizer,
template, indice e tre shard `.safetensors`, sia la cartella superiore `model/`
del repository ufficiale.

Il dispositivo si sceglie sia in **Ricerca semantica RAG** nelle Preferenze sia
con i pulsanti **CPU / GPU NVIDIA CUDA** nella finestra **Documenti del progetto**.
La scelta vale per tutti i progetti, si salva subito e non interrompe lavori attivi.
Nella stessa finestra puoi attivare/disattivare **Indicizza immagini e pagine
illustrate con Ovis**, attivo di default. Dopo una modifica premi **Aggiorna indice**.
La stima nelle Preferenze considera i pesi effettivamente usati e la memoria libera.
Il backend testuale carica circa 6,2 GB di pesi a precisione ridotta su GPU,
oppure circa 12,3 GB in float32 su CPU, più lo spazio di lavoro. I tempi CPU
possono essere lunghi su raccolte grandi. Non è previsto offload automatico
durante il calcolo GPU. Il processo si chiude dopo la ricerca e all'annullamento.

Salva e aggiorna il progetto, oppure invia una domanda con RAG attivo: l'indice
viene ricostruito automaticamente quando cambi embedding. I documenti sono
trasformati in vettori da 2048 dimensioni, conservati nel database locale;
la ricerca combina somiglianza semantica e parole chiave. Caricamento e
indicizzazione compaiono nell'avanzamento del progetto o della risposta.

Con immagini RAG attive, Ovis indicizza testo e contenuti visivi: ogni pagina PDF
con foto, tracciati vettoriali o diagrammi viene renderizzata mantenendo il rapporto
tra i lati e associata al numero di pagina. Le figure Word vengono associate al
blocco di origine. Sono accettati anche PNG/JPEG/WebP originali nei progetti
(massimo 32 MB e 20 milioni di pixel per singola immagine). Le pagine sono
processate a risoluzione contenuta, fino a circa 0,6 MP; dettagli minuscoli possono
non essere recuperati. Audio e video non vengono indicizzati.

Le immagini pertinenti appaiono in **Fonti e file**, accanto alle citazioni. Vengono
copiate nell’output della chat e inviate al modello soltanto con Vision attivo e
compatibile, rispettando il limite di riferimenti; immagini non inviate sono
segnalate esplicitamente. Con un provider LLM esterno, le immagini selezionate e
gli estratti vengono inviati al provider soltanto se Vision è abilitato.

La ricerca mantiene un unico spazio di vettori da 2048 dimensioni per testo e
immagini. Gli indici precedenti vengono aggiornati al prossimo utilizzo o con
Aggiorna indice, senza reimportare gli originali. Le pagine prive di testo possono
essere cercate visivamente, ma non ricevono una trascrizione OCR né una didascalia
inventata. Gli encoder audio e generazione restano esclusi. Disattivando immagini
RAG si torna al solo testo e viene escluso anche l’encoder visivo.

Il RAG GPU e le generazioni locali vengono serializzati. Con memoria a richiesta,
i modelli precedenti sono scaricati prima di Ovis; in modalità residenti restano
caricati e occorre VRAM sufficiente. La stima considera anche il modulo visivo
quando attivo. La lettura dei PDF rimane CPU, il calcolo degli embedding segue
il dispositivo scelto. Il modello ufficiale e i suoi pesi restano invariati.

Fonte e licenza: [Ovis ufficiale, Apache 2.0](https://huggingface.co/ATH-MaaS/Ovis-Omni-Embedding-3B).

## Ricerca web anche senza progetto

Premi **Web** oppure chiedi una ricerca esplicita, se il riconoscimento automatico
è attivo. Le fonti indicano se è stata letta la pagina o soltanto un risultato di
ricerca. In una chat di progetto, **Fonti e file → Salva fonti web nel progetto**
salva gli snapshot realmente letti con titolo e URL e li indicizza. La ricerca
continua a funzionare anche nelle chat senza progetto. Si possono usare insieme
fonti del progetto, PDF allegati e risultati web, entro il budget del contesto.

## Interprete numerico

**Strumenti → Interprete numerico** oppure «Usa l'interprete per calcolare…» chiede
all'LLM selezionato di preparare il calcolo. L'app esegue una sintassi Python limitata:
numeri, liste/dizionari, assegnazioni, `for/range`, comprensioni, condizioni, funzioni
matematiche, `print`, somme e arrotondamenti. Risultati e coordinate dei grafici
provengono dal calcolo eseguito. Il codice e i risultati JSON sono scaricabili.
Non è un kernel Python generale: niente file, rete, pacchetti esterni, classi o
codice arbitrario. Operazioni e dimensioni dei dati sono limitate. Il pulsante
**Calcola** riesegue un blocco `python-calc` senza una nuova chiamata LLM.

## PDF → animazione Manim completa

Installa **Manim** e **LaTeX** da Setup → Interprete e animazioni. Restano nella
cartella dell’app: non richiedono Python o TeX di sistema né modifiche permanenti
al PATH. Manim Community 0.21 usa TinyTeX/TeX Live 2026 e dvisvgm 3.6, scaricati
con versione e hash verificati.

Seleziona **Strumenti → Animazione Manim**, oppure nomina Manim nel prompt:

> Ricava dal PDF allegato un’animazione Manim di 30 secondi. Usa una scena 3D
> con camera in movimento e formule LaTeX. Mantieni esatti i dati del documento.

Lo stesso LLM della chat genera Python `Scene` o `ThreeDScene`: API Manim,
trasformazioni, `ValueTracker`, updaters, `ThreeDAxes`, `Surface`, `ImageMobject`,
`Tex` e `MathTex`, oltre alle librerie del runtime. Le pagine PDF possono essere
lette da Vision, se abilitato. I dati illeggibili non vengono inventati dall’app.
La durata richiesta prevale sul preset; l’MP4 viene verificato e la durata
effettiva viene indicata quando differisce da quella richiesta. Una differenza
di durata non elimina un video valido. RAM e tempo massimo sono
modificabili nelle preferenze. Un errore lascia codice e log consultabili.

Con **Canvas** attivo, video e codice compaiono soltanto nel canvas. Apri **Sorgente**,
modifica il blocco `manim-python`, torna all’anteprima e premi **Renderizza animazione**.
Il codice modificato viene eseguito direttamente, senza un secondo LLM. Puoi
scaricare MP4, `.py`, configurazione JSON, formule `.tex` e log di rendering.
Il commento `# h3_scene: NomeClasse` seleziona la scena se il file ne contiene più
di una. Gli storyboard JSON precedenti conservano il pulsante di rendering.

Quando chiedi una nuova animazione o una ricreazione, il vecchio programma Manim
viene escluso dal contesto fornito al modello, mantenendo richieste e fonti.
Quando chiedi modifiche specifiche, il sorgente precedente resta disponibile.
Gli esempi Python da illustrare vengono conservati. Le istruzioni Manim prevalgono
sulle regole di formattazione della chat ordinaria anche quando sono presenti
documenti. La varietà e qualità della regia restano dipendenti dal LLM scelto;
il renderer esegue il codice generato senza imporre una sequenza di scene.

Il codice libero usa AppContainer Windows: lettura delle librerie e scrittura
nella sola cartella temporanea del lavoro. I dati privati dell’app sono esclusi;
solo gli allegati selezionati vengono copiati come `assets/asset-N.ext`. Un Job
Object limita RAM/tempo e termina i processi figli all’annullamento. Non permette
modifiche ai file del PC, installazione di pacchetti o accesso alla rete. LaTeX
lavora senza shell escape; pacchetti TeX non presenti devono essere installati
nel runtime prima del rendering. Cairo è il default CPU e supporta anche scene
3D; OpenGL GPU richiede driver e un contesto grafico compatibili.

**Video MiniMax H3** accetta singoli clip da 1 a 15 secondi. Una durata esplicita
aggiorna il preset per quella richiesta; oltre 15 secondi la chat mostra un errore
chiaro quando non è allegata una colonna sonora. Con un audio da conservare,
il motore standalone divide il video in scene da massimo 15 secondi e copre
la durata della traccia con memoria visiva e montaggio automatico.
[Voce, audio in Manim e video multiscena](voice-and-soundtracks.md).

## Riquadri e visualizzazioni

Oltre a codice, Mermaid, KaTeX e grafici numerici, i blocchi Markdown
`> [!NOTE]`, `[!TIP]`, `[!IMPORTANT]`, `[!WARNING]`, `[!CAUTION]`, `[!QUOTE]`,
`[!RESULT]`, `[!DEFINITION]` vengono visualizzati come riquadri dedicati.
I documenti completi non vengono caricati ai provider LLM: vengono inviati gli
estratti selezionati e le eventuali immagini Vision necessarie.
