# Modificare singoli clip di un video

Sotto un video MiniMax H3 composto da clip salvati, nella chat o nel canvas,
premi **Modifica clip**. Seleziona i tratti, scrivi le modifiche e scegli i
riferimenti. Le immagini e la canzone originali sono già disponibili; puoi
aggiungere immagini dalla galleria o dal PC.

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
