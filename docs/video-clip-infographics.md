# Infografica e sostituzione degli spezzoni

Apri **Modifica clip** o **Riprendi timeline**, clicca un segmento e scegli la
versione da usare. Con **Solo un tratto** delimita anche l’intervallo: i tempi
delle scritte nel prompt sono relativi a quel tratto, a partire da zero.

Sotto l’anteprima trovi:

- **Esporta spezzone**: crea nella chat un MP4 scaricabile con l’audio originale
  corrispondente. Il file è disponibile anche nella galleria.
- **Modifica con Infografica**: descrivi scritte, split screen, animazioni e
  composizione; i pulsanti nella modale permettono di scegliere layout, stile e
  palette. Il video viene collegato automaticamente, usando la versione scelta
  e i suoi tempi esatti. L’LLM scrive HTML libero, animato dall’interprete
  dell’infografica. Il progetto RAG della chat segue le preferenze dell’account.
- **Sostituisci da PC / Galleria**: inserisce un video già pronto come nuova
  versione dello spezzone. Può essere anche un’infografica o un rendering Manim
  creato separatamente. Non avvia il modello video.

L’infografica compare nel canvas durante la composizione. Puoi modificarla
graficamente e regolare tempi ed effetti. Dopo averla modificata, premi
**Esporta / aggiorna MP4**, poi **Usa nella timeline**. Il controllo verifica
che l’MP4 includa la versione attuale dell’HTML; una vecchia esportazione non
viene inserita per errore.

Il risultato inserito appare nella tendina delle versioni dello spezzone e
mantiene **Riprendi timeline**. Puoi confrontarlo con l’originale, scegliere una
versione precedente come base e guardare **Anteprima timeline**. Quando hai
finito, premi separatamente **Monta video completo**: le altre clip sono
riutilizzate e la canzone originale resta continua.

Le operazioni passano dalla coda condivisa, con una richiesta alla volta per
account. Export, adattamento e inserimento usano CPU; l’infografica usa il modello
LLM configurato e il renderer interno. Non richiedono una nuova generazione
MiniMax. Durante una richiesta puoi consultare e preparare la timeline; questi
comandi si abilitano alla fine della tua elaborazione.

La durata è allineata ai fotogrammi della timeline a 24 fps. Il file importato
viene adattato senza deformarlo, con margini quando necessari: se è più lungo
si usa l’inizio, se è troppo corto viene segnalato. Una sostituzione parziale
conserva i fotogrammi prima e dopo l’intervallo. L’audio del file sostitutivo
non sostituisce la canzone: per cambiare anche il suono usa il Remix audio.

Gli originali e i preset dei modelli restano conservati. File, riferimenti e
versioni sono risolti nella sola area dell’account autenticato.
