# Infografiche Motion Graphics · sperimentale

## Impaginazione classica con più pannelli

La griglia mantiene il contenitore comune scritto dall'LLM, i margini di
intestazione/footer e gli spazi fra celle. I pannelli non vengono più staccati
dal loro contenitore perdendo font, selettori CSS e fondali. I titoli globali
mantengono la loro altezza naturale: una barra flex alta poche righe non viene
allungata a tutta la scena. Un piccolo spazio misurato corregge anche eventuali
collisioni fra titolo e sottotitolo impilati con line-height troppo stretta.

La correzione vale per canvas e renderer offline; ripetere la preparazione non
cambia progressivamente le misure. Ordini e tempi di ingresso dei pannelli e
video autorizzati restano conservati. La modalità a pannello singolo non applica
questi adattamenti. Nuove istruzioni al pianificatore richiedono spazi riservati
per overlay globali e contenuti locali; un layout HTML arbitrariamente errato
può comunque richiedere una revisione. Gli MP4/HTML già esportati vanno
riesportati: i loro pixel e script salvati non cambiano con l'aggiornamento.

Nelle impostazioni Infografica scegliere **Motion Graphics** in Motore animazione.
Classico resta il valore predefinito e conserva i progetti HTML/SVG esistenti.
La nuova modalità usa una scena libera: gruppi, livelli, forme, testi, immagini
autorizzate, barre, contatori e camera hanno keyframe modificabili. Le indicazioni
del prompt prevalgono; allegati e fonti RAG selezionati restano nel contesto.

Il modello produce esclusivamente dati JSON validati. Nessun JavaScript generato
viene eseguito. Lo stesso valutatore temporale produce anteprima, seek e MP4:
i keyframe della versione2 non vengono compressi o troncati come nodi legacy.
Le tracce mantengono il primo valore prima del primo keyframe e l'ultimo dopo
l'ultimo; le proprietà senza tracce usano il valore base. Così un ingresso
ritardato da opacità0 non mostra l'oggetto prima del suo avvio.
La camera supporta pan/zoom; `parallax` dei gruppi principali varia da0 a2.
I grafici numerici restano deterministici; dati inventati per una dimostrazione
devono essere esplicitamente indicati come illustrativi.

Nel canvas si possono scegliere oggetto/camera, modificare tempi, valori, curve,
livelli e parallasse, annullare/ripetere modifiche locali e salvarle. Poi
**Esporta / aggiorna MP4** usa il progetto e gli audio esistenti senza nuove
chiamate LLM/TTS. Le modifiche locali vanno salvate prima di cambiare pagina.

La voce viene generata prima della scena. Le durate sono misurate sull'audio;
i cue disponibili per frase vengono passati al pianificatore. I movimenti
interni restano una regia stimata: nessuna pretesa di allineamento per parola.
Senza voce la durata è manuale. Il progetto memorizza esplicitamente questa
distinzione.

## Sprite riutilizzabili, solo per scelta

La raccolta è privata per account e separata dai progetti. Dal canvas selezionare
un gruppo e **Salva gruppo come sprite**. Viene conservata la posa corrente:
nome, descrizione del soggetto, stile e tag devono essere controllati e confermati
prima del salvataggio. I colori vengono ricavati dai dati della grafica.
Non è una descrizione Vision automatica né una promessa di riconoscimento
semantico infallibile. Si cercano nome, descrizione, stile, tag e colori.

In impostazioni usare **Raccolta sprite** per visualizzare e scegliere quelli
adatti. Nessun elemento viene riutilizzato automaticamente. Le istanze sono
copie dei dati originali espanse nel progetto: eliminare un elemento dalla
raccolta non modifica i progetti già salvati.

La raccolta supporta sprite vettoriali e immagini raster già presenti nel progetto.
Le immagini vengono copiate in un archivio condiviso con nomi basati sul contenuto,
così rimuovere l’allegato originale non elimina la copia dello sprite. Eliminare
lo sprite rimuove la voce e i dati della raccolta; le immagini condivise rimangono
per non rompere i progetti salvati. La caption Vision automatica opzionale resta
un’estensione futura: le descrizioni attuali sono confermate dall’utente.

## Limiti della prima versione

- Scene con massimo256 oggetti,4096 keyframe e512000 byte; errore esplicito se
  il budget viene superato, senza scarti silenziosi.
- Al massimo12 immagini distinte per scena,16MiB ciascuna e64MiB complessivi.
  Le immagini vengono decodificate prima del rendering. Un controllo CPU
  misura l'ingombro dei testi e segnala quelli fuori dal viewport anche con
  la camera, chiedendo al modello una sola correzione mirata.
- Da1 a30 scene e massimo600 secondi, come il motore classico.
- Forme SVG strutturate e gruppi; non ancora importazione generica di SVG esterni,
  scheletro libero completo, maschere/filtri avanzati o curve personalizzate.
- Video di sfondo, split screen e raccolte sfondi restano nella modalità classica.
- La qualità di una composizione generata richiede verifica visiva. Demo scritte
  a mano, test con provider simulato e generazioni reali sono prove distinte.

La prova P0 esporta10 secondi1080p30fps e verifica300 fotogrammi decodificati;
la demo dati-centri P1 usa tre scene originali senza copiare il video indicato.

## Narrazione e musica

Regia e audio permette di scegliere voce femminile, maschile o mista, oltre alla
recitazione. Dalle impostazioni Voice conserva il campione predefinito; Mista
alterna i due campioni fra le scene, iniziando dalla voce predefinita. Ogni scena
mantiene la propria voce anche quando viene divisa in frasi. I riferimenti devono
essere configurati in Voice prima del lancio. Le istruzioni vocali esplicite nel
prompt prevalgono sui selettori. Non si tratta ancora di un dialogo a due voci
all'interno della stessa scena.

Calda richiede affetto, espressività, registro grave e ritmo lento usando i tag
nativi Higgs; il campione determina il timbro e le impostazioni vocali esplicite
conservano la priorità. Queste indicazioni non garantiscono una resa identica per
ogni campione. I metadati e la timeline audio conservano le identità effettive.

La base strumentale richiede una descrizione musicale anche senza jingle. Se la
regia la omette, viene richiesto un solo completamento dei campi musicali prima
di avviare la voce o la musica. Se resta incompleta il lavoro si ferma subito.
La regia completa viene conservata in regia.json nella cartella del lavoro.

## Personaggi articolati e ritmo rapido (sperimentale)

### Le tre modalità di presentazione

Il selettore principale Infografica distingue **Normale**, **Decorativa** e
**Piano sequenza · 2.5D**. Normale conserva il comportamento precedente e i
vecchi progetti Motion rimangono leggibili. Decorativa usa il motore HTML/CSS/SVG
con illustrazioni curate e contenuti animati; Piano sequenza mantiene lo stesso
motore compatibile, aggiungendo piani `data-depth` distinti, una camera con
posizione e velocità continue e brevi dissolvenze a pieno quadro. I raccordi
non aggiungono fasce sfocate, nebbia, ombre o colori di copertura. Il fotogramma
inferiore resta opaco mentre entra il successivo, evitando il fondale grigio
che apparirebbe facendo sparire entrambi. La camera muove solo i piani visivi;
i testi HUD rimangono fermi rispetto al viewport.
La camera e la profondità usano lo stesso codice in anteprima completa e MP4.

Cambiare modalità non azzera video allegati, adattamento, audio, loop, ordine o
numero dei pannelli: anche griglie e video rimangono disponibili. La modalità
sequenza controlla tre profondità dichiarate nelle scenografie vettoriali. Con
uno sfondo immagine sono sufficienti il piano immagine e i contenuti HUD:
non si costruiscono pareti e cieli SVG opachi davanti alla foto. Il wrapper
immagine ha `data-layer-role="background-image"`, l'eventuale fondale SVG
`data-layer-role="background-vector"` e viene tenuto sotto l'immagine. Le
illustrazioni assegnate a una scena devono essere presenti nel suo HTML;
un'omissione riceve una correzione limitata, poi un errore esplicito. Il controllo strutturale non
può certificare da solo la qualità artistica o la corretta separazione dei soggetti.
Con i video si mantengono gli orologi globali e i decoder già esistenti.
Il selettore avanzato dei personaggi articolati resta un esperimento separato.

Si tratta di un piano sequenza **simulato in 2.5D**, composto da ambienti e
raccordi in dissolvenza: non ricostruisce un ambiente 3D navigabile. Illustrazioni
piatte rimangono piatte; il risultato richiede piani grafici separati e una buona
regia. Una demo composta a mano non prova automaticamente la qualità del modello.
L'anteprima della singola pagina mostra quella pagina; «Tutto il filmato · camera
e raccordi» riproduce il percorso globale. Voice e musica esistenti sono riusate
senza generazioni ulteriori durante l'export.

Nelle impostazioni Infografica, **Personaggi → Articolati** abilita Motion Graphics
e la scena libera. La regia definisce al massimo due nuove identità: gli sfondi
vengono richiesti senza persone e il modello immagini genera separatamente un
foglio di sei parti coerenti. La CPU rimuove il magenta e registra i ritagli;
testa, busto, braccia e gambe hanno gruppi e perni gerarchici. La scena conserva
un solo atlante raster per identità e i gesti diventano normali keyframe SVG.
Sono disponibili posa naturale, saluto e indicazione; non camminata o labiale.

La suddivisione generativa non è garantita: maniche o segmenti troppo lunghi
possono richiedere correzione. Controllare il personaggio ruotato/animato nel
canvas prima di archiviarlo. **Salva personaggio animabile** apre la conferma
con nome e descrizione: nessun salvataggio automatico nella raccolta. La copia
salvata include atlante, ritagli e giunture e può essere selezionata per riusi
futuri. Il progetto originale conserva il proprio personaggio incorporato.

**Ritmo → Rapido · stile YouTube** richiede alla regia frasi brevi, battute visive
ogni 2–4 secondi, dettagli e zoom sugli sfondi, HUD leggibile e raccordi coerenti.
Le transizioni Zoom continuano nella stessa direzione con dissolvenza; non
accelerano artificialmente la registrazione vocale. Il tempo delle scene segue
la narrazione realmente prodotta. La qualità e il ritmo della regia generata
richiedono comunque verifica: un esempio composto a mano non prova la resa del
percorso automatico.

Il selettore **Modello per le immagini** è accanto a **Immagini**, nelle opzioni
principali, e resta selezionato passando fra Normale, Decorativa e Piano sequenza.
Normale conserva la generazione precedente, guidata da prompt, allegati e fonti
RAG. Non richiede personaggi. L’animazione articolata è facoltativa, nelle opzioni
del motore Motion Graphics; con il motore Classico i suoi controlli sono nascosti.

Durante la scrittura HTML le tre modalità aggiornano il documento già visibile:
non ricreano l’iframe a ogni sondaggio dello stato. La bozza precedente rimane
visibile durante il caricamento degli asset o il riavvio di una correzione. La
scrittura in tempo reale rimane attiva. A scena pronta vengono montati i normali
controlli di anteprima, che i sondaggi invariati non azzerano.

Anche l’arrivo di nuove voci, musica o contenuti di altre scene mantiene il
documento visibile: vengono confrontate solo le dipendenze grafiche della pagina
selezionata. Le modifiche ai suoi testi, immagini e tempi continuano invece ad
aggiornare l’anteprima. Nel canvas con zoom lo scorrimento appartiene a un solo
contenitore, con spazio stabile per la barra, per evitare cambi di larghezza
durante la crescita dei contenuti.
