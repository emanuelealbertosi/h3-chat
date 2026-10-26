# Lotti immagini e sfondi riutilizzabili

In modalità **Slide**, apri **Immagini**, accanto a **Crea sfondi**. La modale
permette di creare lotti, importarli e gestire catalogazione e RAG. Inserisci
nome, quantità, formato, modello e istruzioni e premi **Genera solo il lotto**:
non vengono create slide. **Usa le fonti RAG** usa il progetto della chat durante
la pianificazione delle illustrazioni. Gli estratti passano al piano una volta;
le immagini vengono poi generate in sequenza, secondo le impostazioni del modello.

In **Impostazioni Slide → Origine delle illustrazioni**, scegli **Usa lotti
immagini salvati** e seleziona da uno a otto lotti con anteprime. Questa scelta
esclude nuove generazioni di immagini, anche se il precedente preset aveva
Illustrazioni AI attivo. Con descrizioni disponibili e catalogazione del lotto
attiva il modello assegna le figure alle pagine per contenuto; negli altri casi
si usa la rotazione nell’ordine salvato, indicata nell’interfaccia. I lotti e il
criterio restano nei dati della presentazione; la selezione si conserva nelle
ultime impostazioni e nei preset.

I lotti generati vengono conservati
automaticamente, anche se interrotti dopo alcune immagini; la libreria recupera
anche i vecchi lotti presenti nelle chat. Puoi rinominarli oppure creare un lotto
selezionando immagini dalla galleria. I file originali restano al loro posto.

**Esporta lotto ZIP** salva gli originali, l’ordine, il prompt di ogni immagine,
le ricette disponibili e le didascalie in `manifest.json`. L’esportazione degli
sfondi è disponibile anche in **Crea sfondi → Raccolta sfondi salvati**.
**Importa lotto ZIP** verifica le impronte SHA-256, carica i file nella galleria e
ricrea la raccolta. Le ricette importate sono metadati di riferimento, non vengono
applicate ai modelli. Le cornici importate mantengono margini e opzioni e si
ritrovano nella selezione **Raccolta** delle slide. L’importazione è limitata a
128 immagini, 32 MB per immagine e 256 MB complessivi; gli ZIP estranei al formato
H3 non vengono importati come lotti.

## Descrizioni e scelta delle figure

Il **prompt originale** conserva ciò che era stato richiesto. **Analizza con
Vision** usa invece il modello chat Vision selezionato e la sua configurazione
per descrivere il contenuto effettivo. Vision deve essere abilitata; con un
provider esterno le immagini vengono inviate al provider. L’operazione entra
nella coda normale, senza avviare generazioni di immagini, e conserva ogni
descrizione completata anche in caso di errore o interruzione. Le descrizioni
possono essere corrette manualmente. Didascalie Vision, importate e modificate
sono indicate separatamente; un prompt di generazione non viene spacciato per
una descrizione verificata.

Scegli un progetto e premi **Aggiungi al RAG**: le immagini con didascalia sono
ricercabili anche con RAG testuale o ricerca per parole, mantenendo il collegamento
alla figura. Ovis ed EmbeddingGemma 2, con immagini abilitate, possono indicizzare
anche direttamente il contenuto visivo. Un embedding non è automaticamente un
modello che scrive didascalie. Senza didascalie e senza RAG multimodale, l’app
chiede di completare la catalogazione invece di fingere una selezione pertinente.
Si aggiungono fino a 30 immagini per operazione RAG. Aggiornare una descrizione
invalida l’indice precedente; aggiorna il progetto prima della ricerca successiva.

Nella modifica di una slide, **Immagini → Da un lotto** permette anche di scegliere
manualmente una figura. Le impostazioni Slide possono assegnare le figure usando
direttamente le descrizioni del lotto; il RAG di progetto resta disponibile anche
per la ricerca nelle fonti. Gli sfondi decorativi continuano a
ruotare nell’ordine scelto: la rotazione degli sfondi è distinta dalla ricerca
delle illustrazioni pertinenti.

## Esportazione SVG e impostazioni

Negli export statici PDF/PPT gli elementi con animazioni CSS vengono portati
a uno stato visibile prima di copiare gli stili; i cicli continui vengono
campionati durante il ciclo. Il canvas originale e l’HTML animato mantengono
le animazioni. Sfumature e riferimenti SVG interni restano locali e i diagrammi
posizionati in assoluto vengono catturati entro il proprio riquadro nel PPT.
Le animazioni native di PowerPoint restano differite.

I collegamenti API sono raccolti nella scheda **Provider API**. **Preferenze**
raggruppa i controlli per chat/immagini, media, RAG, calcolo, strumenti e accessi.
Le impostazioni non vengono duplicate fra Setup e Preferenze e le bozze restano
disponibili cambiando scheda. I download RAG mostrano byte ricevuti e avanzamento;
quando la dimensione totale non è ancora disponibile, la barra è indeterminata.
# Eliminazione dei lotti

La raccolta immagini e la libreria dei set di sfondi offrono selezione multipla,
Seleziona tutti ed Elimina selezionati. È disponibile anche Elimina lotto accanto
all'esportazione ZIP. La conferma mostra nomi, immagini distinte, spazio sul disco
e riusi in altri lotti, artefatti o progetti RAG.

La scelta predefinita rimuove solo il lotto e conserva i file. Per cancellarli
fisicamente occorre selezionare **Elimina anche i file dal disco** e confermare il
pulsante che indica l'eliminazione di lotti e file. Le immagini condivise vengono
segnalate: cancellandole dal disco diventano indisponibili anche negli altri usi.
Non vengono cancellate cartelle intere o immagini non appartenenti alla selezione.

La cancellazione fisica è bloccata durante lavori/indicizzazioni del workspace;
un lotto in lavorazione o usato da un job non può essere rimosso. Il piano viene
ricontrollato al momento della conferma: se file o riferimenti sono cambiati,
occorre riaprire la modale. Un file che Windows non permette di cancellare resta
nel lotto, con una segnalazione che consente di riprovare. La rimozione logica
impedisce che il lotto ricompaia dal recupero dei vecchi job.

