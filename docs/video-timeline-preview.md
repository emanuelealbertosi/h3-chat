# Anteprima della timeline

In **Modifica clip** o **Riprendi timeline**, clicca una clip nella timeline: subito sotto si apre un ventaglio con l’originale e tutte le versioni create. Ogni scheda mostra l’anteprima, la data quando disponibile e l’indicazione **In uso**. Clicca la scheda per sceglierla; **Anteprima** riproduce il singolo spezzone senza audio, mentre **Chiudi** richiude il ventaglio. Le schede scorrono orizzontalmente quando sono molte, anche sul telefono. Puoi spostarti con le frecce, scegliere con Invio e chiudere con Esc.

Il pallino su ogni clip indica quante nuove versioni esistono, escludendo l’originale: **0** significa nessuna modifica creata, **1** una nuova versione, **2** due alternative. Scegliere l’originale non azzera il contatore e non cancella le alternative. La selezione aggiorna anteprima, base della prossima modifica, bozza e montaggio finale; non avvia generazioni. La tendina delle versioni nell’editor è stata rimossa.

Le nuove versioni salvano l’ora di creazione. Per le versioni storiche, quando manca questo dato, viene mostrata la data del file conservato (indicata nel suggerimento della data). Se il dato non è disponibile, la scheda lo segnala senza inventarlo. Il server già in esecuzione può continuare a fornire versioni senza date fino al prossimo aggiornamento a coda libera.

Premi **Anteprima timeline** sotto i segmenti per riprodurre le versioni scelte, comprese le modifiche già salvate, con una sola traccia audio originale.

- **Intero video**: guarda tutta la sequenza aggiornata.
- **Clip aperta**: guarda il segmento aperto nell’editor o il tratto che hai delimitato al suo interno.
- **Intervallo**: indica inizio e fine, per esempio `0:12` e `0:35`, per controllare un raccordo fra due segmenti.

Puoi mettere in pausa, spostarti sulla barra temporale e regolare o disattivare l’audio. Cambiare la versione di una clip aggiorna l’anteprima; le altre alternative restano disponibili. I prompt delle modifiche non ancora generate non cambiano le immagini dell’anteprima.

**Monta video completo** resta il comando separato per creare il file finale. Guardare l’anteprima non accoda un montaggio o una generazione.

Puoi anche [esportare, decorare con Infografica o sostituire uno spezzone](video-clip-infographics.md)
direttamente sotto l’anteprima della clip, conservando durata e canzone originale.

## Preparare le modifiche per dopo

**Salva bozza** conserva prompt, clip selezionate, intervalli, versioni, immagini di riferimento, fotogrammi guida e impostazioni. La bozza è separata per video, chat, utente e taglio dei video importati. Si salva nell’app: puoi chiudere la modale, aggiornare la pagina o riprenderla da un altro dispositivo autenticato con lo stesso account.

Premendo **Crea nuova versione** o **Genera spezzoni**, l’editor salva automaticamente tutte queste impostazioni prima di accodare il lavoro. Se il salvataggio non riesce, il lancio non parte e viene mostrato il motivo. **Salva bozza** resta disponibile per conservare preparazioni che non vuoi ancora generare.

Ogni clip conserva anche i parametri del suo ultimo lancio: modello, risoluzione, passi, seed, attenzione/VEDA, LoRA, PDD, dettagli del campionamento, risoluzione della guida e stato Assistant. Se riapri una timeline senza bozza, l’editor recupera le richieste già registrate, comprese quelle interrotte, e propone le impostazioni della clip aperta. Una bozza esplicita ha la precedenza. Le modifiche che fai ai controlli non vengono sovrascritte cambiando clip; **Ripristina parametri dell’ultimo lancio di questa clip** permette di recuperarli in un clic. I parametri di altre clip restano memorizzati separatamente. Le versioni generate già scelte nella timeline restano selezionate.

Queste funzioni si abilitano quando il server aggiornato espone il relativo supporto; aggiornare l’interfaccia non riavvia il lavoro in corso. Le richieste già accodate conservano comunque il proprio payload originale e restano recuperabili dopo l’aggiornamento.

Alla riapertura la bozza viene caricata. **Ripristina bozza salvata** annulla le modifiche fatte dopo l’ultimo salvataggio. **Riparti dal video** elimina la bozza e riapre l’editor dalle versioni del video salvate. Il messaggio sotto i pulsanti segnala le modifiche non salvate.

Puoi consultare l’anteprima, preparare e salvare la bozza durante una generazione. I comandi di generazione e montaggio si abilitano quando termina la tua richiesta; salvare o ripristinare una bozza non usa i modelli e non accoda lavori.
