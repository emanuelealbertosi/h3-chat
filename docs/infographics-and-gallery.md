# Infografiche e galleria

## Creazione

Premi **Infografica** e descrivi obiettivo, pubblico, contenuti e stile.
Il formato iniziale è **9:16**, con tre scene e durata indicativa di 30 secondi.
Puoi scegliere anche 16:9, 1:1, 4:3 e 16:10. Una richiesta esplicita di
infografica viene riconosciuta anche nella modalità Automatico.

Il modello LLM pianifica una regia e scrive direttamente HTML/CSS e SVG:
la composizione non usa un modello grafico fisso. Allegati, fonti web e RAG
alimentano lo stesso contesto delle slide. Le immagini disponibili vengono
descritte con Vision, se abilitata, con cache e analisi limitata a otto nuove figure;
le altre rimangono inseribili nel canvas. Fonti e figure restano distinte
dalle illustrazioni generate dall’AI.

Puoi lasciare automatici stile e palette o scegliere un trattamento professionale,
giocoso, fumettoso, editoriale, pubblicitario o tecnologico. Il prompt può specificare
colori, font, forme morbide o nette, atmosfera e composizione.

**Immagini → Automatiche** usa quelle fornite e genera illustrazioni se mancano
e un modello immagini è configurato. **Allegati / galleria** usa quelle disponibili;
**Genera con AI** prepara un unico piano e un batch con il modello selezionato.
Il batch locale rilascia gli altri motori, poi ripristina l’LLM per comporre l’HTML.

## Split screen e ordine degli ingressi

In **Infografica → Impostazioni → Composizione dello schermo** scegli due o tre
riquadri affiancati, sopra/sotto, oppure principale con un riquadro sovrapposto.
L’LLM progetta contenuti, colori, immagini ed effetti dentro ciascun riquadro;
il motore mantiene soltanto la disposizione scelta e i suoi confini.

Le scene 9:16 vengono progettate per tutta la superficie verticale. Prima di
accettare una scena video a schermo intero, l’app ne misura l’impaginazione reale:
se i contenuti restano compressi in alto con un grande vuoto, oppure il body usa
dimensioni diverse dal formato scelto, chiede all’LLM una ricomposizione. La regia,
le fonti, le immagini e la narrazione restano conservate. Il controllo non impone
un template e lascia valide composizioni illustrate, formati orizzontali e split
screen. Se il modello lascia ancora troppo spazio vuoto, il canvas lo segnala.

**Comparsa dei riquadri → In sequenza** abilita ordine e intervallo fra ingressi.
Con tre riquadri puoi scegliere 123, 132, 213, 231, 312 o 321. I numeri indicano
la posizione fisica, da sinistra a destra o dall’alto in basso; in 231 entra prima
il centrale, poi il destro e infine il sinistro. Gli intervalli si adattano alle
scene brevi. Ogni riquadro rimane visibile dopo il proprio ingresso.

Puoi allegare fino a tre MP4 e indicare nel prompt quali usare nei riquadri.
I clip proseguono fra le scene e conservano le proporzioni con **Mostra intero**.
Solo il video principale può mantenere il proprio audio originale; gli altri
rimangono muti. Puoi combinare video, immagini, testi e diagrammi.

In **Video → Partenza dei video**, **Insieme** conserva la linea temporale comune.
**All’ingresso del pannello** tiene ogni video sul primo fotogramma fino al suo
ingresso, poi lo riproduce da zero. Anche l’audio originale del video principale
aspetta il suo ingresso. La scelta è disponibile anche nel canvas per le
infografiche già create; premi **Esporta / aggiorna MP4** per aggiornare il filmato.

L’intervallo fra ingressi è impostabile da 0,2 a 30 secondi e segue l’ordine scelto.
Puoi scrivere «fai partire un video ogni 3 secondi» o «delay di 3 secondi fra i
video»: il prompt abilita gli ingressi in sequenza e la partenza al pannello.
Le scene troppo brevi comprimono i tempi per mostrare tutti i pannelli.
La durata totale resta una scelta separata: per vedere integralmente tre clip
da 15 secondi con partenze a 0, 3 e 6 secondi serve almeno una scena da 21 secondi.
**Ferma l’ultimo fotogramma / Ripeti** resta indipendente dalla partenza; il video
prosegue fra le scene dalla prima comparsa dello stesso abbinamento video-pannello.

## Usare un video già pronto

In **Infografica → Video di sfondo**, premi **Allega video** oppure scegli un
MP4 dalla **Galleria** e aggiungilo al messaggio. Il limite è 64 MB. Se alleghi
più filmati, seleziona quello da usare: non viene scelto un file arbitrario.
Il video diventa lo sfondo continuo delle scene, con testi e grafiche HTML sopra.
Non richiede MiniMax o un nuovo modello video. Vision può descrivere il primo
fotogramma; questa modalità non analizza il contenuto di tutto il filmato.

- **Mostra intero** conserva le proporzioni e aggiunge spazio ai lati se necessario.
- **Riempi · ritaglia** riempie il formato scelto senza deformare il filmato,
  con un ritaglio centrale fisso che non segue il soggetto.
- Se il filmato è corto, puoi fermare l’ultimo fotogramma o **Ripeti**.
- L’audio originale è escluso di default. Puoi mantenerlo oppure abbassarlo
  durante la nuova voce. Con Ripeti, anche l’audio originale si ripete.

La durata continua fra le scene: il video non ricomincia a ogni pagina. Il canvas
mostra un’anteprima muta del filmato con le sovraimpressioni; il MP4 esportato
include il montaggio audio scelto. Le esportazioni statiche usano il primo
fotogramma. Quando riesporti dopo una modifica, il video di ingresso resta
collegato e non viene scambiato con il precedente risultato.

Esempio: «Usa il video allegato per un’infografica pubblicitaria 9:16 di 30 secondi.
Lascia il filmato visibile e aggiungi titoli su piccoli pannelli semitrasparenti.
Prima scena: il problema. Seconda: i vantaggi. Terza: invito all’azione.»

La pianificazione ha un budget breve distinto dall’output finale. Se l’LLM
si ripete o restituisce una regia incompleta, l’app interrompe quel tentativo
e ne esegue un secondo senza vincolo JSON. I limiti LLM salvati restano invariati.

## Animazione e audio

**Video animato** combina movimenti degli elementi e transizioni fra scene.
Fade, slide, zoom, pan, blur, wipe, apparizione progressiva e strobe sono
eseguiti dall’interprete locale, senza eseguire JavaScript prodotto dall’LLM.
L’effetto typewriter rivela progressivamente una riga; non genera battiture sonore.
Strobe viene richiesto all’LLM soltanto quando indicato nel prompt.

Puoi scegliere voce seria, vivace, da spot o calda; il motore vocale rimane
quello impostato nelle Preferenze, Higgs di default. La durata con narrazione
segue il parlato realmente generato e può differire dalla durata indicativa.
Le scene vengono sincronizzate con i tempi del TTS.

Musica: nessuna, traccia allegata, base generata o jingle cantato.
La base e il jingle usano il modello musica configurato. Una traccia allegata
può essere scelta anche dalla galleria. Il montaggio attenua il sottofondo durante
il parlato; gli effetti sonori procedurali possono essere assenti, discreti o marcati.
La generazione è accodata insieme agli altri lavori, con un lavoro per account.

**Statica** mantiene la composizione modificabile senza sintetizzare voce o video.
Puoi esportarla come le slide: HTML, PDF, PowerPoint e immagini.

## Canvas ed esportazione

Le scene compaiono progressivamente nel canvas durante la scrittura dell’HTML.
Se il modello restituisce soltanto CSS, una pagina troppo grande o una risposta
troncata, l’app chiede una volta di riscrivere la sola pagina completa. La correzione
conserva musica, voce, allegati e scene già pronte; Max token resta invariato.
Il controllo riconosce elementi HTML reali, non testo che assomiglia a un tag dentro
il CSS. Se anche il secondo tentativo fallisce, la scena viene indicata come
interrotta e la bozza resta nel canvas con un messaggio specifico.
Usa **Modifica grafica** per spostare e ridimensionare blocchi, modificare testi,
inserire immagini e impaginare. Fuori dalla modifica grafica, **Anteprima** e il
cursore mostrano l’animazione della scena selezionata. Il MP4 include anche
transizioni e montaggio audio dell’intera infografica.

In **Tempi ed effetti degli elementi** modifica ingresso, durata, uscita ed effetto.
Gli angoli del video possono essere dritti, morbidi o arrotondati, anche dopo
la creazione. MP4 conserva un fotogramma rettangolare: gli angoli esterni alla
grafica sono riempiti con lo sfondo chiaro o scuro scelto, senza trasparenza alpha.

**Esporta / aggiorna MP4** renderizza le modifiche senza rigenerare LLM, immagini,
voce o musica. Il player mostra l’ultimo video esportato; dopo una modifica
serve una nuova esportazione. Il rendering usa Microsoft Edge presente in Windows
e PyAV nel runtime privato. Stop chiude anche tutti i processi del renderer privato.
Il video viene pubblicato soltanto quando completo.

**Ricrea questa scena animata con AI → Ricrea solo questa scena** riscrive
soltanto la scena selezionata, compresi tempi ed effetti. Conserva le altre scene,
la voce, la musica e il filmato già generati. Per aggiornare il filmato premi
separatamente **Esporta / aggiorna MP4**. Se il modello
restituisce HTML statico senza animazioni utilizzabili, l’app chiede una correzione
prima di accettare il risultato. Lo stesso comando aggiorna il filmato dopo
le modifiche grafiche manuali. Nel canvas la vista iniziale mostra tutti gli elementi:
premi **Anteprima** per riprodurre la scena.

## Galleria

**Galleria**, accanto ad Allegati, raccoglie file caricati, documenti importati via
browser nel RAG, risultati generati ed esportazioni. Cerca per nome e filtra per
tipo e origine; seleziona uno o più file per aggiungerli al prompt in qualsiasi
modalità. Le immagini sono disponibili anche da **Modifica grafica → Immagini
della slide → Galleria**. Le gallerie degli account rimangono separate.

I file esistenti sono referenziati senza copie. Le esportazioni create dal browser
vengono archiviate nella galleria fino a 64 MB; sopra questo limite il download
rimane disponibile, con un avviso che il file non è stato archiviato. Libri più
grandi si importano dalla sezione RAG, che ha limiti separati. Le sorgenti RAG
collegate direttamente a percorsi esterni del server non vengono esposte nella galleria.
Eliminare una chat non cancella i file conservati in galleria.

## Higgs: personalità e ritmo

Voice offre personalità seria, vivace, spot e calda, oltre ai controlli personalizzati.
Nel Setup i parametri avanzati Higgs includono seed e fattore di ritmo tra 0,90
e 1,15, applicato preservando l’altezza della voce. Seed -1 mantiene il seed
del campione. I valori delle installazioni esistenti restano invariati.
I preset e i controlli di Higgs suggeriscono una recitazione: l’enfasi parola per
parola non è garantita e va valutata all’ascolto con il campione vocale scelto.

## Voce radio

In Infografica → opzioni avanzate → Recitazione, scegli **Radio · +8–12%**.
Higgs usa seed 734, temperatura 0,7, pause di 150 ms e ritmo alternato
1,08 / 1,12 fra le frasi, senza cambiare l'altezza della voce. Le indicazioni
emotive variano fra entusiasmo, calore, orgoglio e decisione. Il risultato
dipende anche dal campione vocale: l'enfasi su singole parole non è garantita.
Il profilo è disponibile anche nelle opzioni Voice e come preferenza predefinita.
Le preferenze esistenti restano invariate.
