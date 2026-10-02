# Progetti, fonti e animazioni

## Progetti e RAG

Premi **＋ accanto a Progetti**, assegna un nome e salva. Puoi scrivere istruzioni
condivise e collegare file o cartelle con **Collega e indicizza**. PDF, Word `.docx`,
testo e codice sono supportati. Gli originali restano nei loro percorsi; l'indice
SQLite viene salvato nella cartella dati dell'app. Le cartelle vengono ricontrollate
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
non necessariamente tutto il progetto. PDF scansionati senza testo richiedono
Vision tramite allegato alla chat; l'indice RAG non esegue OCR.

Limiti: 500 documenti per progetto, 25 MB per documento, cartelle fino a quattro
livelli, massimo 12 estratti per risposta. Indicizzazione fallita o file cancellati
non restituiscono vecchi contenuti. Percorsi mancanti/errori sono visibili nella
gestione del progetto.

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
La durata richiesta prevale sul preset; l’MP4 è verificato e, se troppo corto,
la scena generata viene corretta fino a due volte. RAM e tempo massimo sono
modificabili nelle preferenze. Un errore lascia codice e log consultabili.

Con **Canvas** attivo, video e codice compaiono soltanto nel canvas. Apri **Sorgente**,
modifica il blocco `manim-python`, torna all’anteprima e premi **Renderizza animazione**.
Il codice modificato viene eseguito direttamente, senza un secondo LLM. Puoi
scaricare MP4, `.py`, configurazione JSON, formule `.tex` e log di rendering.
Il commento `# h3_scene: NomeClasse` seleziona la scena se il file ne contiene più
di una. Gli storyboard JSON precedenti conservano il pulsante di rendering.

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
chiaro, senza generare silenziosamente un clip più corto. Per 30 secondi di
animazione matematica scegli Manim.

## Riquadri e visualizzazioni

Oltre a codice, Mermaid, KaTeX e grafici numerici, i blocchi Markdown
`> [!NOTE]`, `[!TIP]`, `[!IMPORTANT]`, `[!WARNING]`, `[!CAUTION]`, `[!QUOTE]`,
`[!RESULT]`, `[!DEFINITION]` vengono visualizzati come riquadri dedicati.
I documenti completi non vengono caricati ai provider LLM: vengono inviati gli
estratti selezionati e le eventuali immagini Vision necessarie.
