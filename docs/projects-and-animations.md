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

## PDF → animazione Manim

Installa **Manim** in **Setup/Preferenze → Interprete e animazioni**. È un componente
privato opzionale di circa 113 MB: non servono Python, TeX o FFmpeg di sistema.
Allega il PDF e scrivi, per esempio:

> Ricava dal PDF una breve animazione Manim. Spiega l'area del cerchio in due scene,
> con testo, cerchio e formula. Usa i dati del documento.

Puoi scegliere anche **Strumenti → Animazione Manim**. Si riutilizza lo stesso LLM
della chat, locale o API. Il testo del PDF viene estratto sul PC; le pagine senza
testo, o figure richieste indicando la pagina, possono essere fornite al modello
Vision, se attivo. I dati illeggibili non vengono ricostruiti dall'app.

L'LLM produce uno storyboard JSON validato: massimo 12 scene, testi, formule
MathText, cerchi, rettangoli, frecce e grafici di funzioni. Manim anima gli oggetti
in sequenza e pulisce il canvas tra le scene. Le coordinate dei grafici vengono
calcolate; le formule non richiedono una distribuzione TeX. Non viene eseguito
Python Manim generato liberamente. Non sono ancora supportati immagini nella
scena, oggetti 3D, voce narrante, trasformazioni complesse o tutta l'API Manim.

Default: CPU/Cairo, 8 secondi, 854 × 480, 15 fps. Durata, risoluzione, fps e
CPU/OpenGL GPU si cambiano nelle preferenze. OpenGL richiede un contesto grafico
compatibile. Video, JSON e pulsante **Renderizza animazione** sono disponibili
nel risultato. Gli LLM piccoli possono omettere parti della richiesta; uno schema
valido non garantisce da solo una lezione corretta e completa.

Con **Canvas** attivo all'invio, risultato e MP4 vengono mostrati solo nel canvas;
nella chat resta il messaggio standard. Con Canvas spento sono visibili nella chat.
Le istruzioni sono richiudibili; il MP4 si può riprodurre e scaricare.

## Riquadri e visualizzazioni

Oltre a codice, Mermaid, KaTeX e grafici numerici, i blocchi Markdown
`> [!NOTE]`, `[!TIP]`, `[!IMPORTANT]`, `[!WARNING]`, `[!CAUTION]`, `[!QUOTE]`,
`[!RESULT]`, `[!DEFINITION]` vengono visualizzati come riquadri dedicati.
I documenti completi non vengono caricati ai provider LLM: vengono inviati gli
estratti selezionati e le eventuali immagini Vision necessarie.
