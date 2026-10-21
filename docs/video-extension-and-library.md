# Nuove clip e raccordi

Apri **Modifica clip / Riprendi timeline**, seleziona una clip e scegli
**Clip prima** oppure **Clip dopo**. L’inserimento avviene al confine della
clip intera. Le versioni selezionate nella timeline sono la base del lavoro.

Puoi aggiungere **5, 10 o 15 secondi** in tre modi:

- **Estensione video**: usa cinque fotogrammi del video adiacente come un
  unico blocco temporale nativo di MiniMax, ancorato all’inizio o alla fine
  della generazione. Il contesto viene rimosso dall’uscita, quindi non viene
  duplicato nella timeline. Il costo di memoria è leggermente superiore a
  quello di una clip indipendente della stessa durata.
- **Clip autonoma**: nuova scena da prompt, con i soli riferimenti scelti;
  non eredita tutte le immagini del filmato.
- **Primo / ultimo fotogramma**: immagini proprie dal PC o dalla galleria,
  oppure ultimo frame della clip precedente e primo della successiva.
  Quando manca un vicino, quel lato resta libero. Anche la stessa immagine
  può guidare entrambi i lati. I fotogrammi guidano il modello, senza garantire
  una copia esatta dei movimenti o un raccordo perfetto.

La guida audio è facoltativa, dal PC o dalla galleria; il lip-sync richiede
questa guida. Senza guida viene usato l’audio generato da MiniMax. L’Assistant
è disattivabile. Modello, risoluzione, passi, seed, PDD e attenzione valgono
solo per questa richiesta: i preset salvati restano invariati. I LoRA di
editing che richiedono un video allineato non si applicano a nuove scene.

Si genera soltanto la nuova clip, poi si monta una nuova timeline. Le clip
esistenti vengono riutilizzate e l’audio originale successivo al punto di
inserimento si sposta insieme alle scene. La timeline precedente resta intatta.
L’operazione usa la coda condivisa e il motore locale MiniMax H3.

# Galleria

Il pulsante **Galleria** nel menu laterale apre una raccolta navigabile
di file caricati e generati. Accanto agli allegati resta disponibile la
selezione di più file da aggiungere al prompt. Filtra per tipo e origine,
cerca, carica dal PC e apri un file per visualizzarlo. Nel player trovi
precedente/successivo, download, **Usa in chat** e, per i video, modifica / estensione,
ricreazione, remix e upscale. La ricreazione richiede una generazione con
istruzioni salvate; per un file esterno usa la modifica video.

Puoi rinominare l’etichetta nella raccolta o rimuovere un elemento. La rimozione
lo nasconde dalla galleria anche dopo la sincronizzazione; conserva i file
usati dalle chat e dai lavori, evitando di rompere riferimenti già salvati.
Le raccolte rimangono separate per utente.

# MOV e anteprime durante la generazione

I MOV vengono caricati e passati al motore nel loro formato originale. Se il
browser non li riproduce, **Prepara anteprima compatibile** crea su CPU una
copia MP4 H.264/AAC, memorizzata in cache; l’originale resta il file da modificare.
Se il codec è già compatibile, viene cambiato solo il contenitore video.

Nella risposta in corso, **Clip pronte** apre un solo player con pulsanti per
le clip completate. Durante le modifiche non vengono proposte le clip originali
non ancora rigenerate. La lista si aggiorna ogni dieci secondi soltanto mentre
è aperta; video e audio vengono caricati solo quando scegli una clip. Il
montaggio finale continua. La riproduzione si interrompe chiudendo il riquadro
o cambiando chat.
