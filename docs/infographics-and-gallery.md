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
