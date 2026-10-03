# Slide HTML nel canvas

Allega PDF, documenti Word `.docx` o immagini e chiedi, ad esempio:

> Crea 10 slide in 4:3 da questi documenti, con formule, immagini e un diagramma.

Oppure scegli **Strumenti → Slide · HTML in tempo reale**, imposta il numero
(1–30; default 8), il formato (16:9 predefinito, 4:3, 16:10, 1:1), lo stile e
il dettaglio del testo. Le scelte esplicite nel prompt prevalgono sui controlli. Il canvas
si apre automaticamente; nella chat resta il messaggio di accompagnamento.

Come la creazione V2 di H3-Slides, l'LLM progetta prima la sequenza, poi ogni
pagina con un albero di gruppi, colonne, titoli, testi, immagini, codice e
diagrammi. Il browser interpreta questi elementi come HTML, mostrando anche
il testo ancora in scrittura. Il sorgente è dichiarativo e modificabile: non
viene eseguito HTML, CSS o JavaScript arbitrario prodotto dal modello.
H3-Slides non deve essere installato.

## Contenuto e stile

**Sintesi** è il valore predefinito. **Testi completi** chiede paragrafi,
spiegazioni ed esempi nel corpo delle slide: non li riduce a headline e non li
nasconde nelle note. Puoi chiedere «Crea 5 slide con testi completi, stile
fumettoso» oppure «Presentazione discorsiva, seria e professionale». Lo stile
non impone la brevità: ogni stile supporta entrambi i livelli di dettaglio.

Sono disponibili gli stili **Serio / professionale**, **Giocoso / colorato** e
**Fumettoso**, tre palette (petrolio, indaco, corallo) e caratteri moderni o
editoriali. Il prompt può specificare altri toni e indicazioni di contenuto;
il canvas applica i preset visivi disponibili. Colori e font dei singoli
elementi sono modificabili nell'editor.

Il renderer misura lo spazio dopo aver caricato font, figure e diagrammi.
Riduce moderatamente la composizione e, se necessario, crea pagine di
continuazione, conservando testo, codice, elenchi e tabelle. Il numero richiesto
indica i capitoli logici: una pagina densa può produrre più pagine fisiche
nell'anteprima e nei download. Il canvas indica quante continuazioni ci sono.

## Fonti

- PDF/Word: testo, tabelle e figure incorporate; i PDF senza testo possono
  fornire pagine a Vision attraverso il normale trattamento degli allegati.
- Immagini della conversazione: analizzate in gruppi compatibili con il limite
  di riferimenti del modello. Vengono riutilizzati il medesimo LLM e il normale
  proiettore Vision su CPU; nessun secondo LLM. Con Vision disattivata o non
  disponibile le figure sono inseribili ma il contenuto non viene interpretato;
  la risposta lo segnala.
- RAG: estratti delle fonti selezionate nel progetto corrente. Una richiesta
  generica di slide può recuperare una panoramica dell'indice; restano validi
  selezione delle fonti, budget del contesto e isolamento del progetto.
- Web e trascrizioni: disponibili con i normali controlli della chat.

La presentazione conserva il catalogo delle fonti e le note per pagina.
I riferimenti RAG nelle note e nel testo aprono gli estratti utilizzati.
Sono supportati Markdown, codice evidenziato, LaTeX, Mermaid e grafici Chart.js
con dati verificabili. Il modello deve rispettare le fonti; i controlli sui
riferimenti non certificano tutte le affermazioni.

Le fonti molto lunghe vengono selezionate entro il contesto dell'LLM. Non vengono
lette necessariamente tutte le pagine: la chat conserva i dettagli sugli
estratti e sulle pagine Vision. Le figure incorporate sono limitate a 16 per
documento e 32 per richiesta, oltre alle immagini riutilizzate della chat;
non includono ogni oggetto vettoriale o ogni grafico disegnato nel PDF. Per un
grafico specifico indica la pagina nel prompt e usa Vision. L'indice RAG non
esegue OCR sui PDF scansionati. Usa almeno 2048 token di risposta per pagine
ricche; se si raggiunge il limite, l'anteprima viene conservata con l'avviso.

## Navigazione, modifiche e download

Usa frecce/menu delle pagine e **Segui scrittura** per seguire la nuova pagina
oppure mantenere quella scelta. La cronologia del canvas conserva anche le
presentazioni precedenti. Se una generazione si interrompe, restano le pagine
completate e l'ultima anteprima.

Con il canvas attivo e Strumenti su Automatico puoi scrivere «Riduci il testo
della seconda pagina» oppure «Aggiungi una slide sui risultati». Il modello
ricompone la presentazione usando il contenuto esistente; le versioni precedenti
restano nella cronologia. **Sorgente slide** consente modifiche dirette al JSON
dentro il blocco `h3-slides`, con controllo degli elementi e delle immagini.

**Modifica grafica** seleziona gli elementi della pagina: modifica testo o
codice, font, dimensioni, colori e allineamento; usa le maniglie ↕ e ↘ per
spostare e ridimensionare. Puoi aggiungere testo, duplicare o eliminare
elementi, cambiare tema/stile/caratteri e annullare o ripetere le modifiche.
Il salvataggio è automatico in una copia di lavoro nella cronologia; la versione
generata resta recuperabile. Durante la generazione l'editor è disabilitato.

**HTML** scarica un documento autonomo con figure e font incorporati, apribile
offline nel browser. **PDF** produce una pagina per slide nel formato scelto,
con testo e diagrammi vettoriali quando disponibili. **PNG** esporta l'intera
sequenza come immagine; **Word** contiene immagini delle pagine per conservarne
la composizione. **PowerPoint** esporta `.pptx` con testi, riquadri e grafici
dati nativi modificabili, oltre a note e fonti. Formule, diagrammi Mermaid e
immagini restano oggetti grafici spostabili e ridimensionabili. I caratteri
moderni/editoriali usano Arial/Cambria nell'export PowerPoint per portabilità;
codice Courier New e stile fumettoso Comic Sans MS, se disponibile sul PC.
**.md** conserva il sorgente dichiarativo. Le pagine di continuazione sono
incluse in tutti gli export e non nascondono il testo.

Funziona con LLM locali oppure provider API, secondo la normale configurazione.
Per gli allegati serve il componente Documenti incluso nell'installazione;
per l'esportazione PDF serve Microsoft Edge.
