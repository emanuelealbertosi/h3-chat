# Seed e ricette delle immagini

Nelle impostazioni **Immagini** della chat puoi scegliere **Usa un seed fisso**,
inserire un numero o premere **Usa ultimo seed**. Il recupero riguarda l'ultima
immagine completata con il modello selezionato, anche in un'altra conversazione
della stessa area utente. Disattivando il seed fisso si torna a `-1`, cioè casuale.
La stessa scelta è nelle Preferenze generali: lì premi **Salva** per confermare
il predefinito del modello. Le scelte della chat e le istruzioni nel prompt
mantengono la priorità sulle Preferenze generali.

Per recuperare una vecchia immagine apri **Dati di creazione** sotto l'immagine
in chat o nel canvas, oppure nella sua anteprima in galleria. **Riusa impostazioni**
prepara il modello originale, il prompt effettivo, i parametri e il seed di quella
specifica immagine. Ripristina riferimenti e LoRA, sostituendo quelli nella bozza.
Assistant viene disattivato per evitare una nuova riscrittura del prompt.
Non parte nessuna generazione: controlla la bozza e premi **Invia**.
Una vecchia direttiva «seed casuale» nel prompt viene sostituita dal seed effettivo
recuperato. I membri di un lotto hanno ciascuno la propria ricetta.

Se il modello, i riferimenti o i LoRA non sono più disponibili, oppure il seed
effettivo non era stato registrato, l'app indica il dato mancante e non sostituisce
silenziosamente la ricetta con i valori attuali. Uno stesso seed non garantisce
pixel identici con versioni differenti dei modelli, dei motori o dei backend.

## Conservazione dei dati

I nuovi PNG locali includono il campo testuale `h3_creation`, contenente la
ricetta JSON, e una copia affiancata `image.png.h3.json`. L'inserimento conserva
i blocchi compressi dell'immagine senza decodificare o ridisegnare i pixel.
Ricaricando un PNG che contiene la ricetta, l'app può leggerla anche senza il
messaggio originale. I riferimenti restano file separati e devono essere disponibili.
Il prompt e il negative prompt sono parte dei metadati del PNG.

**Scarica dati (.json)** esporta la ricetta per immagini e video. Per i vecchi
risultati l'app cerca i dati nella cronologia e nei piani salvati, senza inventare
quelli assenti. Il semplice file PNG/JPEG/MP4 di una vecchia generazione può non
contenerli: conserva anche il JSON. Il video non viene ricodificato o modificato
per aggiungervi questi dati; seed e impostazioni delle singole clip sono nel JSON
quando erano stati registrati. Chiavi API e percorsi assoluti non vengono esportati.
