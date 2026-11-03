# Locandine

Scegli **Locandine** nella chat e apri **Impostazioni Locandine**. Scrivi il
contenuto nel prompt, allega eventuali foto/loghi e invia. È disponibile anche
in Basic; Advanced mostra modello immagini e margine di sicurezza.

- Formati: A3/A4 verticali o orizzontali, 4:5, 9:16, quadrato e 16:9.
- Da una a sei varianti complete, sfogliabili nello stesso canvas.
- Stili: automatico dal prompt, editoriale, evento, culturale, promozionale,
  fumetto e minimalista.
- Immagini: automatico, allegate, nuove illustrazioni oppure solo grafica.
  In Automatico gli allegati hanno precedenza; in assenza di allegati si usa
  il motore immagini disponibile. Senza motore o in CPU si usa tipografia/SVG.
  La scelta esplicita di generare richiede il motore e il permesso immagini.
- Le impostazioni della modale restano salvate nel browser. Formato, quantità
  e richieste esplicite di immagini nel prompt prevalgono sui valori salvati.

La composizione predefinita è **Grafica ricca HTML/CSS · come nelle slide**.
Il modello scrive liberamente HTML/CSS/SVG per tutta la pagina: sfondi,
decorazioni, forme, gradienti, tipografia espressiva e livelli sopra le immagini.
Non dipende dai riquadri di un piano MOSS. Lo stile esplicito del prompt
prevale, quindi sono consentite anche composizioni sobrie o minimaliste.
Le immagini possono occupare tutta la pagina; velature e pannelli locali
servono alla leggibilità senza coprire volti o dettagli importanti.

Il testo viene composto in HTML/SVG separatamente dalle immagini. Usa
**Modifica grafica** per intervenire su testi, colori e posizioni; **Ricrea
questa locandina con AI** applica una modifica alla sola variante selezionata.
Il flusso non passa dalla scaletta e dalla pianificazione didattica delle slide.
L’Agente dispone di `create_posters` e può riusare artefatti e fonti.

PNG esporta la variante corrente; PDF esporta ogni variante pronta su una
pagina separata. Nei formati A3/A4 viene impostata la misura fisica della pagina
e vengono conservati i testi e gli elementi vettoriali compatibili. HTML è
autonomo e sfogliabile. PowerPoint conserva ogni variante pronta come immagine
a pagina intera, a risoluzione tripla: mantiene effetti, font, sfondo e formato
A3/A4, ma non rende le singole scritte modificabili in PowerPoint. Il testo
originale compare anche nelle note. Per cambiare il poster usa l'editor H3.
Per le presentazioni HTML è disponibile lo stesso export fedele; l'alternativa
**PowerPoint modificabile** ricostruisce gli elementi e può differire nella resa.
Non vengono aggiunti abbondanze, crocini o conversione
CMYK: per una stampa tipografica controllare le richieste dello stampatore.
La risoluzione delle illustrazioni resta quella del modello o degli allegati.

Esempio: «Crea 2 locandine A3 per questo evento, stile editoriale, usa le foto
allegate. Titolo: … Data: … Luogo: …». Non vengono inventati date o contatti
mancanti. Per una variante solo grafica: «Crea una locandina 9:16 senza immagini».

La composizione dipende dal modello LLM scelto. Il canvas conserva le varianti
completate anche in caso di interruzione. Le prove di interfaccia, esportazione
e CPU usano dati sintetici; una prova con un modello reale va verificata anche
visivamente, senza confonderla con il collaudo automatico.
# Composizione completa con MOSS

Nelle impostazioni Locandine, **Composizione → Avanzata · piano MOSS con aree riservate**
usa un unico piano spaziale per sfondo, soggetti e aree tipografiche.
L'Assistant prepara prima tutti i testi e poi le aree nel formato finale. Di
default MOSS crea una sola immagine a tutta pagina **senza scritte**. Il
compositore **Espressivo** usa HTML/SVG come le slide ricche: titoli sagomati,
colori, contorni, gradienti, effetti e titoletti coordinati alla grafica. Non
si limita a una scelta fissa di font. I testi restano separati dall'immagine.

**Chi disegna le scritte → MOSS per brevi titoli** è un'opzione esplicita:
titoli, slogan o etichette brevi vengono dipinti da MOSS e rimangono pixel.
Il testo lungo e i dati precisi restano HTML/SVG. Il compositore **Stili
predefiniti** mantiene invece l'impaginazione deterministica dei profili.
Il compositore creativo opera nei riquadri del piano senza coprire lo sfondo
con una nuova slide. Prima di generare lo sfondo, se la misura CPU segnala un
testo tagliato, H3 può ampliare quella sola area negli spazi liberi da soggetti
e altri testi. Accetta la modifica solo dopo una nuova misura CPU riuscita.
Questa correzione geometrica non si applica agli sfondi già dipinti.

Richiede modalità GPU, un modello MOSS disponibile e immagini Automatico o Genera.
Il modello, i megapixel e l'intensità della guida si scelgono nella modale. Una
sola immagine allegata può essere usata come guida img2img (numero 1, 2, ecc.;
0 = nessuna). Non equivale a più riferimenti indipendenti: la guida viene
ricostruita, non incollata in un riquadro. Le dimensioni seguono il poster, anche
con una guida di altro formato. Le preferenze globali del modello non cambiano.

L'Agente usa lo stesso percorso con `create_posters`, `composition=moss_layout`,
`image_model`, `reference_image`, `visual_megapixels` e `visual_strength`.
`typography_engine=expressive` e `text_renderer=html` sono i valori predefiniti;
`preset` e `moss_short` selezionano le alternative esplicite.
Il permesso immagini è sempre necessario. Il piano e i testi originali rimangono
nel documento e la ricetta nei metadati dell'immagine. Il controllo font/margini
precede l'inferenza. Nel percorso espressivo un browser locale su CPU misura
i testi reali dentro i riquadri; eventuali omissioni, parole extra o testi
tagliati richiedono una correzione prima di generare lo sfondo. Sono ammesse
solo risorse HTML/SVG statiche locali, senza script, immagini o URL esterni.
I box generativi e la correttezza delle scritte raster restano
approssimativi e richiedono revisione visiva; non sono vincoli tipografici esatti.

Il controllo dei contenuti conserva frasi e paragrafi esatti una sola volta:
l'ordine delle aree nel JSON può cambiare, per esempio mettendo il titolo
prima dell'occhiello, senza modificare le parole. Non è un confronto sul solo
elenco di parole: riscritture, duplicazioni e riordini dentro le frasi vengono
respinti. Titoli, grassetto e punti elenco Markdown vengono trattati come
formattazione. Per programmi densi il compositore espressivo può impiegare un
corpo di 18–21px sul canvas da 1280px; preferisce 22–28px e mantiene il controllo
CPU del testo effettivo. Le collisioni con i soggetti richiedono coordinate
realmente corrette, senza ignorare i vincoli.

Il planner lavora in pixel: l'app applica una sola trasformazione all'intero
piano per inserirlo nel margine sicuro. I box dei soggetti non possono
intersecare i box dei testi; gli sfondi continui restano nella descrizione
generale. Il testo HTML conserva i contenuti e riceve titoletti, paragrafi ed
elenchi con misurazione del font, senza cambiare le aree riservate. La guida
img2img è opzionale: per un layout autonomo da testo si lascia a 0.

Nel percorso a stili predefiniti i colori dei testi HTML vengono verificati contro un campione mediano dello
sfondo reale nella rispettiva area. Se il contrasto è insufficiente, l'inchiostro
si schiarisce o scurisce mantenendo la tinta per quanto possibile. Immagine,
contenuti e coordinate non cambiano. È una misura locale, non una certificazione
di leggibilità su ogni pixel della grafica generativa.

## Stile delle scritte

In **Impostazioni Locandine** sono disponibili Stile delle scritte, Effetti su
titoli e testi brevi, Carattere titoli e Carattere testi. Automatico lascia al
planner la scelta coordinata con la grafica; editoriale, giocoso, cinematografico,
manoscritto, fumetto, rétro, neon e minimale propongono abbinamenti coerenti.
Gli effetti includono ombra, contorno, estrusione, bagliore neon, metallico e
rilievo tipografico. I testi lunghi mantengono una resa leggibile.

Le indicazioni esplicite nel prompt hanno priorità: per esempio «scritte
cinematografiche, titoli in Bebas Neue, corpo in Manrope, effetto metallico».
Le famiglie locali sono Manrope, Cormorant, Bebas Neue, Baloo 2, Caveat e Bangers;
i font aggiunti sono distribuiti con licenza OFL. Le scelte restano salvate.
PNG, HTML e PDF conservano i font; gli effetti HTML sono statici. Il lettering
creato da MOSS rimane generativo e non garantisce identità con le lettere HTML.

Nel canvas **Applica font ed effetti** crea una nuova versione mantenendo
l'esatto sfondo già salvato: in modalità Espressivo usa il LLM selezionato e
verifica la geometria su CPU; non genera una nuova immagine. In modalità Stili
predefiniti l'applicazione avviene solo su CPU, senza nuova chiamata al LLM.
Le versioni precedenti restano disponibili. Le parole già dipinte da MOSS
non possono cambiare con questa operazione. Se il testo è stato modificato
manualmente rispetto al piano, H3 chiede di usare Modifica grafica e non
sostituisce la pagina con vecchi contenuti. La verifica automatica misura
bordi e parole, senza attestare una revisione estetica del risultato.

## Foto modificata dall’Agente

L’Agente può concatenare `edit_image` e `create_posters`. Dopo il ritocco usa
`image_id` come `hero_asset_id`, collega l’artefatto con `source_artifact_ids` e
sceglie `composition=html`, `images=existing`. In questo modo il poster usa il
file ritoccato esatto, senza un secondo passaggio generativo sulla persona.
Se il planner omette la foto selezionata dopo il tentativo di correzione, il job
segnala l’errore. Il collaudo della concatenazione usa un motore simulato; la
fedeltà di un ritocco reale dipende dal modello immagini scelto.


La preparazione dei contenuti mostra ora i caratteri JSON scritti e verifica
i limiti dei singoli campi durante la generazione. Un campo ripetitivo o troppo
lungo viene fermato e riceve una sola correzione, senza tagliare silenziosamente
i testi della locandina. I pallini degli elenchi sono formattazione HTML;
omissioni o modifiche alle parole continuano a essere respinte.

Il piano spaziale ora assegna blocchi di testo identificati: il server inserisce
le parole originali senza farle ricopiare al modello. Prima di dipingere uno
sfondo nuovo può traslare il gruppo illustrato o ridurlo uniformemente fino
al20%, lasciando fermi i testi. La trasformazione è registrata e il piano
deve comunque superare i normali controlli di collisione e misura. Gli sfondi
già creati non vengono riposizionati. Contenuti esatti e ingombro misurato
dispongono di una correzione mirata ciascuno, con massimo3risposte tipografiche.


## Riprodurre o migliorare una locandina allegata
Nelle Impostazioni Locandine scegli Da un riferimento grafico → Riproduci il
layout allegato oppure Migliora il layout allegato. Allega un’immagine o PDF,
selezionalo separatamente dalle fotografie e scegli la pagina PDF. Se esiste
un solo candidato può essere selezionato automaticamente; con più candidati
serve un ID esplicito. Mantieni il formato dell’originale per le stesse proporzioni.
Il modello LLM deve avere Vision abilitata. Esempio: «Riproduci questa locandina,
conserva disposizione e palette; sostituisci il titolo con NOTTE JAZZ». Oppure:
«Migliora questa locandina: stessi contenuti, più gerarchia e contrasto».
Il motore estrae una pagina su CPU; per PDF conserva anche i rettangoli testuali
originali. Vision descrive regioni, colori, testi leggibili e incertezze. Le
immagini individuate vengono ritagliate e riutilizzate, mentre i testi leggibili
sono HTML/SVG modificabili. L’app identifica anche la funzione di figura
principale, logo e QR: una scritta sovrapposta non deve far sparire la figura.
I testi piccoli ricevono una lettura ravvicinata automatica (massimo 24 ritagli,
rispettando il limite Vision configurato); i dati incerti rimangono ritagli
originali, senza una trascrizione inventata. Questo non aumenta la risoluzione
della sorgente. L’originale resta intatto. L’analisi è salvata
con l’artefatto e come layout.json; ambiguità e sostituzioni font vanno nelle note.
La ricostruzione non garantisce identità dei pixel, font proprietari o separazione
perfetta di testi e figure inseparabili. Nuove illustrazioni non sono avviate
implicitamente in queste modalità. Per la brochure multipagina serve ancora un
percorso distinto: il selettore qui tratta una pagina alla volta. L’Agente usa
create_posters con reference_mode, reference_asset_id e reference_page.

Una richiesta breve come «Rifai e migliora questa locandina» usa questo flusso
senza dover preparare ritagli o descrivere manualmente la composizione. Migliora
conserva la struttura semantica; una riprogettazione radicale richiede istruzioni
esplicite. Prima di segnare la pagina pronta, l’app misura su CPU immagini,
contenuti e testi coperti/tagliati, con al massimo due correzioni HTML automatiche.
Se il controllo fallisce conserva la bozza e segnala il limite, senza dichiararla
pronta. La verifica geometrica non certifica la qualità estetica o l’esattezza
dell’OCR. Un logo o una figura con testo inseparabile conserva il testo raster;
non viene presentato come elemento interamente vettoriale o modificabile.

L’analisi usa una copia con assi di coordinate, senza alterare l’originale o i
ritagli riutilizzati. Su Windows l’OCR già presente nel sistema fornisce ulteriori
ancore geometriche; non viene scaricato alcun modello. Se il servizio o la lingua
non sono disponibili, si continua con Vision e la griglia. Le lettere dell’OCR
non sono considerate automaticamente corrette. Una lettura ravvicinata estranea
al testo atteso viene rifiutata, invece di sostituire un calendario con una lista.
Le illustrazioni significative restano risorse anche quando Vision le chiama
decorazioni. Il controllo respinge anche i titoli ristampati sopra scritte raster.

Una miniatura densa con molti testi minuscoli e letture incerte non viene
presentata come una locandina migliorata pronta. H3 chiede il PDF originale o
un’immagine realmente più nitida (un ingrandimento artificiale non recupera le
lettere). Lo stesso avviene se, dopo i dettagli, almeno un quarto dei blocchi
rimane incerto, con almeno quattro blocchi. Riproduci rimane disponibile per
conservare i ritagli raster. I recapiti non verificati non diventano testo nuovo.

Il riferimento appartiene agli allegati della richiesta corrente. Se ricarichi
una richiesta e sostituisci l’immagine, un solo nuovo allegato viene selezionato
automaticamente e la pagina precedente viene azzerata. Con più candidati non
viene scelto arbitrariamente il primo: il selettore richiede una scelta. Le altre
impostazioni restano conservate; un vecchio ID non allegato non viene recuperato
dalla cronologia. Il server applica la stessa regola anche ai client già aperti.

La verifica dei testi raster considera le aree effettivamente mostrate, con
ritaglio, adattamento e mascheratura. Una dicitura ripetuta in un’altra parte
del poster è ammessa; una sovrapposizione vicina alle parole della foto riceve
una correzione automatica e, se persiste da sola, un avviso visivo non bloccante.
Il riconoscimento delle singole lettere raster non è una certificazione ottica.
Testi mancanti, tagliati, coperti e immagini obbligatorie assenti rimangono
problemi bloccanti dopo i tentativi limitati di correzione.
# Esportazione PowerPoint: fedele o modificabile

**PowerPoint fedele** conserva la pagina completa come immagine ad alta
risoluzione. **PowerPoint modificabile** esporta invece i testi HTML come caselle
di testo, i riquadri come forme e le illustrazioni come immagini separate, anche
per locandine già salvate: basta riesportare, senza rigenerarle. Le coordinate
e i corpi dei testi sono rapportati al formato fisico A3/A4 della locandina.

Le immagini restano oggetti grafici: le scritte già dipinte nei pixel e gli SVG
complessi non vengono ricostruiti come testo. Font, gradienti dei titoli e altri
effetti CSS possono essere semplificati nel formato modificabile. Usa il formato
fedele per mantenere l'aspetto esatto. I due pulsanti indicano scelte diverse;
la modalità modificabile non viene più ignorata per i documenti locandina.
