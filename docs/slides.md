# Slide nel canvas

Scegli **Strumenti → Slide** oppure chiedi una presentazione nel prompt. PDF,
Word, immagini, fonti RAG e ricerca web possono fornire il contenuto. Il canvas
si apre automaticamente e mostra la pagina mentre viene scritta; nella chat
resta il testo di accompagnamento. Le versioni precedenti restano nella cronologia.

## Due motori

**LLM · HTML libero** è il default per le nuove presentazioni. Il modello scelto
in chat progetta sequenza e direzione artistica, poi scrive direttamente HTML e
CSS per ogni pagina. Sceglie composizione, palette, font, grafica e SVG: il
renderer non applica il vecchio template. Puoi chiedere stili seri, professionali,
giocosi, colorati o fumettosi e scegliere **Sintesi** oppure **Testi completi**.
La qualità dipende anche dal modello e dai token disponibili; non è una replica
di Gamma. Per pagine articolate aumenta Max token nelle preferenze del modello.

Nelle impostazioni **Slide → Composizione** scegli **Classica** oppure **Ricca ·
stile infografica**. La seconda usa HTML libero e una direzione grafica condivisa
con le infografiche: figure dominanti, diagrammi SVG e dettagli pertinenti, senza
imporre più testo o un template. È indipendente da stile, sintesi e testi completi.
Le nuove immagini richiedono comunque **Illustrazioni AI** e il relativo modello.
La scelta resta nella presentazione salvata, nella bozza recuperata e nelle
rigenerazioni. Puoi anche chiedere «grafica ricca» o «stile infografico» nel prompt;
«grafica essenziale» torna alla composizione classica. Scegliere Ricca attiva il
motore HTML libero; scegliere Deterministico riporta la composizione a Classica.

**Deterministico** conserva il precedente generatore di elementi strutturati,
con temi, colonne e impaginazione automatica. Le presentazioni già salvate senza
un motore esplicito continuano a usare questo percorso. La loro modifica tramite
prompt conserva il motore precedente.

Sono disponibili **1–100 slide** (numero fisso iniziale 8) e formati 16:9
(default), 9:16, 4:3, 16:10 e 1:1. In **Slide → Impostazioni → Numero di slide**
puoi scegliere **Numero fisso** oppure **Automatico · dai contenuti**. In automatico
il modello sceglie il numero durante la scaletta, sulla base di richiesta, fonti,
pubblico ed eventuale durata, senza mirare automaticamente a 50 o aggiungere
riempitivi. Il numero effettivo viene poi usato per contenuti, note, immagini e
composizione; la richiesta automatica resta recuperabile con **Ricarica richiesta**.

Le istruzioni esplicite nel prompt prevalgono per numero, formato e stile:
«Crea 40 slide» impone 40 anche se nelle impostazioni è selezionato Automatico;
«Scegli tu quante slide servono» attiva il conteggio autonomo anche partendo da un
numero fisso. Un numero esplicito superiore a 50 viene segnalato, senza ridurlo
silenziosamente. Le presentazioni già salvate restano valide; una modifica di
testo o grafica conserva il numero attuale, salvo richiesta esplicita di cambiarlo.
In automatico puoi anche indicare un vincolo: «Scegli tu, massimo 20 slide»
oppure «Decidi tu quante slide servono, tra 15 e 25 slide»; il piano deve restare
entro quell'intervallo e comunque entro il limite generale di 50.
Nel motore LLM la pagina mantiene il formato richiesto: eventuali elementi oltre
i bordi vengono segnalati. Puoi correggerli graficamente o chiedere al modello
di adattare la pagina. Il motore deterministico può creare continuazioni per
testi molto lunghi.

La scaletta usa un budget breve e **Thinking Off**, separato dalle impostazioni
delle pagine finali. La cronologia conserva richieste e riepiloghi delle vecchie
presentazioni senza rimandarne tutto l'HTML al modello a ogni generazione.

Con il motore HTML, dopo la scaletta viene preparato un piano editoriale per
ogni pagina: testo visibile effettivo, spiegazioni/esempi pertinenti, proposta
grafica, note relatore e fonti. Ogni risposta ha un budget separato e Thinking
Off; non viene compresso tutto il contenuto in un'unica scaletta breve.
Le illustrazioni vengono pianificate su questi contenuti prima del batch immagini;
la composizione HTML riceve il piano della singola pagina. Le note sono salvate
nel campo dedicato della presentazione, anche prima che l'HTML sia completato.
Un piano troncato interrompe il lavoro con un errore. Il campo fonti è vincolato
agli identificatori del catalogo attuale. Un riferimento fuori catalogo nel
testo o nella risposta di un provider viene corretto con un solo tentativo
mirato; se la correzione non riesce, la bozza e il motivo vengono conservati.
Non vengono creati collegamenti per somiglianza fra codici come S1 e R1.
Scaletta, catalogo, piani completati e candidato non valido sono salvati anche
nel checkpoint `editorial-state.json` del lavoro. Un rilancio identico può
recuperare i piani del lavoro fallito come bozze da ricontrollare sulle fonti
attuali; non vengono considerati automaticamente contenuti già verificati.
Non esiste un limite automatico di 35 parole o tre punti: sintesi/testi completi
e limiti espliciti del prompt guidano la densità. Vecchie direzioni artistiche
non devono introdurre limiti nel nuovo lancio. Gli artefatti precedenti restano
inalterati; per applicare il nuovo flusso occorre una nuova generazione.

## Fonti e immagini

Le figure di allegati e RAG sono disponibili insieme agli estratti testuali.
Vision riusa il modello chat e il relativo proiettore sul dispositivo CPU/GPU
scelto in chat. Le descrizioni preliminari sono brevi, con Thinking Off e un
limite separato dalla risposta finale. Se Vision non è disponibile o una
descrizione è incompleta, la figura resta inseribile e viene segnalata come non
analizzata. Selezione delle fonti, budget del contesto e progetto restano validi.

**Figure Vision → Rapida** analizza fino a otto figure nuove, dando precedenza
alle fonti recuperate per la richiesta attuale. Le altre restano nel catalogo
e sono indicate come non analizzate. **Completa** analizza tutte le figure e può
essere lenta, soprattutto con il proiettore sulla CPU. Le descrizioni completate
vengono conservate localmente e riutilizzate anche se la stessa figura viene
estratta di nuovo in una cartella diversa; cambiare immagine o modello invalida
il riuso. Un provider non Vision salta l'analisi e usa soltanto testo e metadati:
non acquisisce il contenuto visivo delle immagini. La scelta CPU/GPU resta nel
menu **Vision** della chat.

In **Modifica grafica → Immagini · PC, allegati, RAG, Internet** puoi inserire o sostituire figure:

- **Dal PC** apre il selettore file senza filtri di formato o dimensione e conserva
  l'originale in galleria. Per inserirlo nella slide deve essere un'immagine visualizzabile.
- **Allegati** riusa le immagini della presentazione.
- **Dal RAG** mostra le figure già indicizzate del progetto della chat, con ricerca
  per documento/testo associato e paginazione. Non avvia una nuova indicizzazione.
- **Internet** cerca su Wikimedia Commons, conservando autore, licenza e origine.

## Modificare le slide HTML

Se la generazione viene interrotta, apri la presentazione nella cronologia del
canvas e premi **Completa slide mancanti**. Il numero sul pulsante indica le
pagine da completare: quelle già pronte vengono conservate. La ripresa usa il
modello LLM attualmente scelto in chat; non occorre reinviare tutta la richiesta.
Il pulsante resta disabilitato mentre è già in corso un lavoro del tuo account.

Per correggere una sola pagina, selezionala e apri **Ricrea questa slide con AI**.
Scrivi le modifiche e premi **Ricrea solo questa slide**. Le istruzioni restano
separate per pagina quando passi da una slide all'altra. La nuova versione resta
nella cronologia; non sostituisce le altre pagine. Le modifiche locali non ancora
salvate vengono salvate prima dell'invio e diventano la base della revisione.

Durante generazione, ripresa e revisione il canvas mostra la fase corrente e i
caratteri dell'anteprima; la grafica si aggiorna man mano che arriva HTML valido.
**Segui scrittura** segue la pagina in lavorazione; puoi disattivarlo scegliendo
una pagina diversa. A lavoro terminato i controlli di modifica tornano attivi
anche quando l'ultimo aggiornamento non cambia ulteriormente il contenuto.

Nel canvas scegli la pagina e premi **Modifica grafica**. Clicca un elemento:
la maniglia **↕** lo sposta e **↘** ne cambia larghezza e altezza. Apri **Testo e
dimensioni** per modificare testo, font, colori e misure precise. **Seleziona gruppo**
risale al riquadro che contiene l'elemento; puoi premere di nuovo per selezionare
un gruppo più grande.

**+ Testo**, **+ Titolo** e **+ Blocco** aggiungono elementi nel gruppo selezionato;
un blocco contiene un titolo e un paragrafo modificabili. **Duplica**, **Elimina**,
**Sposta prima** e **Sposta dopo** operano sulla selezione. Per aggiungere un'immagine
seleziona un testo o un gruppo; per sostituirla seleziona l'immagine esistente.

In **Impaginazione** scegli una, due o tre colonne, seleziona **Intera slide** o
**Gruppo selezionato**, poi premi **Applica impaginazione**. Il gruppo dispone
i suoi blocchi in ordine, adatta le immagini e compatta il contenuto entro il
formato senza cancellare testo. Nei gruppi automatici, aggiunte e modifiche fanno
riordinare il contenuto; trascinare un blocco ne cambia l'ordine. Se il contenuto
è eccessivo anche con testo leggibile, l'operazione viene annullata e viene chiesto
di dividerlo. Questo comando è una modifica esplicita: il layout HTML originale
del modello resta invariato finché non lo applichi. **Libero · trascinamento**
disattiva il riordino automatico mantenendo la disposizione raggiunta.

**Annulla** e **Ripeti** gestiscono le ultime 30 operazioni della sessione di modifica.
**Applica e salva** conserva la copia di lavoro con i suoi media. Salva prima di
cambiare pagina o terminare la modifica. Durante la generazione l'editor è disabilitato.

## Anteprima ed export

La ricreazione delle slide statiche conserva anche il CSS restituito dal modello
in un blocco separato dall'HTML. Se manca uno stile utilizzabile, richiede una
correzione automatica della sola pagina. Se anche il secondo tentativo ne è privo,
segnala l'errore e conserva la bozza e la versione precedente: non dichiara la
slide completata. Questo controllo verifica la presenza dello stile; non garantisce
che ogni scelta grafica del modello sia corretta.

HTML/CSS sono sanitizzati e renderizzati in un frame locale isolato: niente
JavaScript prodotto dal modello, form, URL remoti, rete o file locali. Le immagini
provengono esclusivamente dal catalogo autorizzato. I font locali Manrope/Cormorant
e KaTeX vengono forniti dall'app; sono disponibili anche i font di sistema.
Nelle slide statiche le immagini vengono mostrate intere con proporzioni
conservate anche quando l'HTML del modello usa `object-fit:cover` o `fill`.
La correzione non cambia le dimensioni dei riquadri e viene conservata negli export.
Le scene animate delle infografiche mantengono il proprio trattamento delle figure.
Il contrasto del testo viene corretto su sfondi solidi quando insufficiente;
gradienti, immagini e composizioni SVG richiedono anche la verifica visiva.

**PDF** conserva formato e grafica della pagina, con testi e SVG vettoriali quando
disponibili. **PowerPoint** contiene testi e superfici modificabili e immagini/
diagrammi spostabili e ridimensionabili; gradienti e grafica complessa possono
diventare immagini. Non tutti gli effetti CSS hanno un equivalente PPTX.
**HTML** è apribile offline con immagini incorporate; **PNG** esporta la sequenza;
**Word** contiene immagini delle pagine. **.md** conserva il sorgente completo.

Funziona con LLM locali o provider API. H3-Slides non è richiesto. Il componente
Documenti è incluso nell'installazione; per il PDF serve Microsoft Edge.

### Esportazione

PowerPoint conserva testi e grafica modificabili, ma non esporta le animazioni CSS come animazioni native di PowerPoint. Il PDF resta statico. L’HTML delle presentazioni è invece sfogliabile e conserva le animazioni CSS già presenti nelle pagine; le frecce, la tastiera e il selettore permettono di consultare una pagina alla volta. «Ripeti animazioni» riapre la pagina. Il file funziona offline e mantiene isolate le slide, senza eseguire codice generato. Le animazioni native del PPTX sono rinviate per scelta dell’utente.

Il PDF elimina le proprietà grafiche predefinite duplicate conservando lo stile calcolato. L’HTML conserva HTML/CSS delle pagine e incorpora immagini e font, condividendo i font comuni per ridurre le dimensioni. Il limite rimane 64 MiB di contenuto HTML, incluse le immagini incorporate.

La durata indicativa della presentazione si imposta da 1 a 20 minuti (0 = Automatico). La durata esplicita nel prompt prevale. Il planner adatta scaletta, contenuti e note, incluse pause e attività. Non imposta un timeout né una riproduzione automatica di quella durata.

Le illustrazioni AI vengono pianificate con un formato per ciascun riquadro (orizzontale, verticale o quadrato), mantenendo il budget di pixel scelto. Nel canvas, selezionando un’immagine in Modifica grafica, puoi scegliere Intera oppure Riempi riquadro e spostare il centro del ritaglio. Il riempimento conserva le proporzioni, senza deformare. Le figure originali restano intere finché non scegli un ritaglio.
