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

**Deterministico** conserva il precedente generatore di elementi strutturati,
con temi, colonne e impaginazione automatica. Le presentazioni già salvate senza
un motore esplicito continuano a usare questo percorso. La loro modifica tramite
prompt conserva il motore precedente.

Sono disponibili 1–30 slide (default 8) e formati 16:9 (default), 4:3, 16:10 e
1:1. Le istruzioni esplicite nel prompt prevalgono per numero, formato e stile.
Nel motore LLM la pagina mantiene il formato richiesto: eventuali elementi oltre
i bordi vengono segnalati. Puoi correggerli graficamente o chiedere al modello
di adattare la pagina. Il motore deterministico può creare continuazioni per
testi molto lunghi.

## Fonti e immagini

Le figure di allegati e RAG sono disponibili insieme agli estratti testuali.
Vision riusa il modello chat e il relativo proiettore sul dispositivo CPU/GPU
scelto in chat. Le descrizioni preliminari sono brevi, con Thinking Off e un
limite separato dalla risposta finale. Se Vision non è disponibile o una
descrizione è incompleta, la figura resta inseribile e viene segnalata come non
analizzata. Selezione delle fonti, budget del contesto e progetto restano validi.

In **Modifica grafica → Immagini · PC, allegati, RAG, Internet** puoi inserire o sostituire figure:

- **Dal PC** apre il selettore file; immagini raster decodificabili dal browser,
  entro 12 MB, vengono normalizzate a massimo 4096 px.
- **Allegati** riusa le immagini della presentazione.
- **Dal RAG** mostra le figure già indicizzate del progetto della chat, con ricerca
  per documento/testo associato e paginazione. Non avvia una nuova indicizzazione.
- **Internet** cerca su Wikimedia Commons, conservando autore, licenza e origine.

## Modificare le slide HTML

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

HTML/CSS sono sanitizzati e renderizzati in un frame locale isolato: niente
JavaScript prodotto dal modello, form, URL remoti, rete o file locali. Le immagini
provengono esclusivamente dal catalogo autorizzato. I font locali Manrope/Cormorant
e KaTeX vengono forniti dall'app; sono disponibili anche i font di sistema.
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
