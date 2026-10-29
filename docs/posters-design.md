# Locandine: proposta di integrazione

Stato: implementato e attivo localmente. Guida aggiornata in [posters.md](posters.md).
La proposta seguente descrive la direzione del prodotto; il riuso diretto dei lotti
come selezione dedicata resta futuro, mentre gli asset dei lotti si possono allegare.

## Esperienza

Pulsante «Locandine» tra le modalità creative, con propria modale. Predefinito
A3 verticale; alternative A4, 4:5, 9:16, quadrato e orizzontale. Una locandina
per richiesta, con varianti opzionali salvate nello stesso lotto del canvas.
Prompt e allegati specificano soggetto, pubblico, stile e contenuti; modello
immagini e RAG seguono le impostazioni già disponibili.

## Direzione artistica

Un manifesto, non una diapositiva: gerarchia tipografica marcata, una figura
protagonista, composizioni asimmetriche, spazio negativo, sovrapposizioni
intenzionali e percorso di lettura chiaro. Stili editoriale, evento, culturale,
commerciale, fumetto e minimalista. Evitare la griglia ripetuta di card delle
slide e i paragrafi didattici quando non richiesti.

Testi, date, indirizzi e loghi rimangono elementi separati dall'immagine IA.
L'LLM compone HTML/CSS/SVG con gli stessi controlli di isolamento e verifica
del motore grafico esistente. Il modello immagini prepara solo i visual;
non gli si affida la scrittura di informazioni minute o essenziali.
Non inventare nomi, date, prezzi, sponsor, contatti o codici QR mancanti.

## Riutilizzo dei motori e qualità

Riutilizzare generazione e ritocco immagini, lotti, catalogo asset, eventuale
RAG/Vision, autore HTML/CSS, anteprima canvas, zoom e revisione. Nuova ricetta
editoriale e nuovi formati, senza alterare la pipeline Slide esistente.

Esportazioni desiderate: PDF con formato fisico di pagina corretto, PNG e HTML
modificabile. Testi vettoriali nel PDF quando possibile. Verificare margini,
font incorporati, risoluzione delle immagini alla misura di stampa e assenza
di tagli. La stampa con abbondanze e profilo CMYK richiede una fase dedicata:
non dichiarare un PDF tipografico professionale prima di questi controlli.

Prima prova: un evento con titolo, data, luogo e CTA, verificando sia A3
verticale sia 4:5; un secondo stile dimostra che non è una copertina slide
riciclata. Nessuna generazione di prova avviata durante questa progettazione.
