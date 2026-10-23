# Modificare singoli clip di un video

Sotto un video MiniMax H3 composto da clip salvati, nella chat o nel canvas,
premi **Modifica clip**. Seleziona i tratti, scrivi le modifiche e scegli i
riferimenti. Le immagini e la canzone originali sono già disponibili; puoi
aggiungere immagini dalla galleria o dal PC.

Per animare un'immagine come primo fotogramma, scegli **I2V · immagine iniziale**
nel clip selezionato. Premi **Carica immagine per questo clip** o **Scegli dalla
galleria**, oppure seleziona una delle immagini già presenti. I2V usa una sola
immagine guida, senza i riferimenti di identità; tornando a **Riferimenti**
ritrovi la selezione precedente. Scrivi nel prompt il movimento desiderato.
Con **Solo un tratto**, l'immagine avvia il tratto scelto, non l'intero filmato.
Il motore riceve un vero fotogramma guida anche con Assistant Off.

Il formato resta quello del filmato originale: un'immagine di proporzioni diverse
viene adattata senza deformarla e può avere margini. Il raccordo con il materiale
precedente e successivo dipende dal contenuto. L'audio e i suoi tempi restano
invariati. I fotogrammi guida vengono conservati anche per **Ricrea video**.

Attiva **Lip-sync** se nel tratto selezionato vuoi vedere cantare il personaggio.
Il condizionamento usa esattamente l'intervallo corrispondente della canzone.
Assistant On prepara le istruzioni con il modello chat corrente; Assistant Off
passa direttamente la descrizione al motore video.

**Crea nuova versione** accoda una normale richiesta. Il modello genera soltanto
i clip selezionati; il montaggio finale riusa gli altri file e la canzone
continua, mantenendo durata e formato. La versione originale resta disponibile.
I nuovi clip sono salvati durante il lavoro: dopo un errore, **Rigenera** recupera
le sostituzioni già completate.

**Intera clip** è la modalità iniziale. Per modificare soltanto una parte,
premi **Solo un tratto**: sposta le due maniglie sotto l'anteprima oppure scrivi
i secondi di inizio e fine. **Riproduci tratto** mostra l'intervallo selezionato.
I tempi sono relativi alla clip; viene mostrata anche la posizione nel film.
Ogni tratto deve durare almeno un secondo e viene allineato ai fotogrammi a 24 fps.

Il modello genera solo quel tratto. Il montaggio conserva i fotogrammi precedenti
e successivi, senza rallentarli o spostarli, poi applica la canzone originale
all'intero video. La clip modificata viene ricodificata; le altre vengono
riutilizzate. Non viene applicata una dissolvenza automatica: il raccordo visivo
dipende dal nuovo contenuto e può essere percepibile. Dopo un errore di montaggio,
**Rigenera** recupera anche il tratto già generato, senza rigenerarlo.

Puoi selezionare un intervallo per clip nella stessa richiesta, fino a 15 secondi
ciascuno. Per più interventi sulla stessa clip, modifica la nuova versione.
Richiede un video completo con checkpoint e riferimenti ancora disponibili,
generato dal motore MiniMax H3 standalone. Ogni utente accede soltanto ai video
e ai riferimenti della propria area.

## Memoria precedente e raccordo finale

In **Rigenera · riferimenti**, con **Intera clip**, puoi attivare **Recupera
memoria dalle clip precedenti**. Il motore rilegge il primo fotogramma della
sequenza corrente e i finali delle ultime due clip disponibili, rispettando le
versioni selezionate in timeline. Usa anche una clip precedente appena rigenerata
nello stesso lancio. L’ultimo stacco precedente delimita la memoria; non vengono
usate clip future. La prima clip non ha memoria precedente. Sugli stacchi la
casella parte disattivata: attivarla significa chiedere esplicitamente una
continuazione da prima dello stacco.

Il **Fotogramma finale per il raccordo** è indipendente e può essere combinato
con la memoria. Scegli **Finale libero**, **Finale attuale della clip**, **Primo
fotogramma della clip successiva**, oppure un’immagine caricata. Le immagini
estratte sono preparate su CPU dalla versione selezionata e restano interne,
senza comparire nella galleria ordinaria. La guida usa l’ultimo fotogramma reale
della clip (359 a 15 s/24 fps), non il padding del modello. Richiede uno dei nove
posti immagine; nessun riferimento viene scartato automaticamente. L’ultima clip
non offre un primo fotogramma successivo.

Memoria e finale guidato sono salvati nella bozza e nell’ultimo lancio e vengono
recuperati dopo un’interruzione. Il montaggio non rigenera automaticamente le
clip successive. I2V e Modifica video mantengono i propri strumenti di guida;
per i tratti parziali usa i fotogrammi guida di Modifica video. Non vengono
applicate dissolvenze o sostituzioni pixel per pixel: il modello interpreta gli
ancoraggi, e una destinazione molto diversa può peggiorare la transizione.
