# Agent H3 — prima versione sperimentale

Agent è una modalità aggiuntiva. Assistant On/Off, chat e tutte le modalità esistenti
rimangono disponibili. Scegli **Agent** tra i pulsanti della chat e apri
**Impostazioni Agent**, oppure anteponi `agent:` al messaggio. Per il cervello usa il
LLM scelto in chat, locale o tramite API; deve produrre JSON strutturato valido.
Con il registro esteso è consigliato un contesto di almeno 32.000 token; modelli piccoli o poco affidabili
nel JSON possono fermarsi senza eseguire strumenti.

Il ciclo è realmente iterativo: il modello sceglie uno strumento, H3 ne verifica
argomenti e permessi, lo esegue, restituisce l'esito e il modello decide il seguito.
Il piano iniziale non fissa una sequenza obbligatoria. Non vengono installati altri
LLM, scaricati modelli o caricati motori aggiuntivi all'avvio di Agent.

## Strumenti disponibili

- Fonti RAG del progetto corrente, documenti allegati, skill incorporate.
- Elenco e lettura degli artefatti della chat; lotti immagini dello spazio di lavoro.
- Creazione, modifica e completamento slide; misura CPU dei contenuti fuori bordo.
- Creazione lotti immagini e ritocco di immagini con Qwen o altro modello edit
  configurato; inserimento del risultato in una pagina tramite revisione.
- Voce letta o composta; musica con il motore scelto; trascrizione degli audio
  allegati o salvati in un artefatto della stessa chat.
- Infografiche statiche o animate proceduralmente, modifica delle scene e nuovo
  rendering; musica generata in base alla durata delle scene e applicata con
  adattamento CPU, senza modificare l'originale.
- Manim attraverso il renderer e l'isolamento già presenti in H3, su CPU.
- Analisi di un'immagine scelta con il modello chat Vision configurato, calcoli
  con l'interprete numerico limitato e ricerca tramite il servizio Web di H3.
- Re-sing sulla melodia di un audio salvato o allegato, con YuE2 locale e gli
  strumenti di separazione/sincronizzazione già pronti. Non installa componenti.
- Ricerca/creazione di progetti, copia degli allegati o di file di artefatti nel
  progetto, catalogazione Vision delle immagini e indicizzazione RAG.
- Creazione di sorgenti/programmi e documenti testuali scaricabili in ZIP, senza
  esecuzione o installazione; PDF tramite il renderer PDF di H3 su CPU.
- Ricerca di immagini Web, download verificato e aggiunta a lotti; importazione
  di pagine realmente lette nel progetto con URL di provenienza.
- Download di documenti originali PDF/DOCX/TXT/Markdown dal Web pubblico, con URL.
- Elenco modelli del catalogo, avvio/stato download verificati e preset immagini/video validati.
- File/comandi Windows e importazione/esportazione con H3, solo nel perimetro scelto.
- Preparazione di collegamenti LLM API con finestra protetta per la chiave.

## File e collegamenti API

Agent deve usare e dichiarare lo strumento H3 specifico quando esiste: slide,
immagini, audio, PDF e calcoli non vanno sostituiti da file fittizi. `create_files`
salva fino a 20 sorgenti/testi e uno ZIP negli output gestiti del workspace.
Non esegue il programma e non scrive in cartelle arbitrarie del PC. Python e JSON
ricevono un controllo sintattico, che non equivale a un test funzionale.
Per file e comandi nella cartella scelta o sul PC usa i pulsanti Sandbox/Globale: vedi [Accesso al computer](agent-computer.md). Il browser grafico e il controllo mouse/tastiera restano separati.

Per un nuovo server LLM l'agente usa `configure_api`, con nome, indirizzo e modello:
compare una finestra compilata da verificare, con il campo chiave separato. La chiave
non è un argomento dello strumento e non entra in prompt, osservazioni o checkpoint.
Viene salvata tramite la protezione credenziali già usata da H3 per Windows/macOS.
Chiudi per ora svuota il campo; puoi riaprire la finestra dalla risposta Agent.
Annulla richiesta ferma il run; Salva e continua registra il collegamento e riprende.
La prova della connessione è un pulsante esplicito e può consumare credito.
Salvare non implica aver verificato il server. Il default globale resta invariato;
la scelta di usare il nuovo modello per quel run richiede la casella nella finestra.
Non è una capacità generale di modifica di tutte le impostazioni dell'app.
La configurazione dei collegamenti è riservata al proprietario, come nelle impostazioni API ordinarie.

## Materiali da Internet

Con Web attivo, oppure una richiesta esplicita di ricerca/download Internet quando
Web automatico è abilitato, puoi chiedere:

> agent: Cerca su Internet immagini sulle porte logiche e aggiungile al lotto
> «Informatica». Conserva la provenienza e poi cataloga quelle utili con Vision.

> agent: Cerca online materiali sulle reti, aggiungi le pagine lette al progetto
> «Reti», crealo se manca, indicizza e controlla le fonti disponibili.

SearXNG può fornire una ricerca immagini dedicata; negli altri provider si cercano
candidati nelle pagine trovate dal servizio Web H3. Etichette e titoli del sito
non sono descrizioni Vision. PNG/JPEG/WebP sono verificati su CPU prima del salvataggio;
il download conserva i byte originali, la pagina di provenienza e l'URL dell'immagine.
Un lotto esistente viene riutilizzato per ID o nome esatto; nomi ambigui richiedono ID.
File non validi, download falliti e risultati mancanti sono riportati nel registro.

Le pagine importate diventano Markdown con URL nel progetto; poi `index_project`
costruisce l'indice. Uno snippet non può essere importato fingendo di aver letto la
pagina. Questa navigazione è recupero di pagine pubbliche: non comprende ancora
login, CAPTCHA, siti che richiedono JavaScript o interazioni con un browser grafico.

## Collegamenti e punto di partenza

Agent riceve l'artefatto selezionato nel canvas al momento dell'invio. Puoi anche
indicargli un lavoro già salvato nella stessa chat oppure partire dagli allegati.
Non serve ricreare i passaggi precedenti: legge il risultato scelto e ne usa l'ID.
Le creazioni accettano `source_artifact_ids`, fino a otto fonti per passaggio:
testi, contenuti e note delle slide e i file associati vengono passati al servizio
successivo. La provenienza viene conservata nel checkpoint. I numeri dei file
si riferiscono sempre all'elenco completo del relativo artefatto.

| Sorgente e destinazione | Collegamento |
| --- | --- |
| Documento → slide, immagini, voce, musica, infografica, Manim | Leggi il documento, poi usa il contenuto estratto come fonte. |
| Audio → slide o altri contenuti | Trascrivi prima; la trascrizione salvata diventa una fonte testuale. |
| Immagine → descrizione → altri contenuti | Analizza con Vision, poi riusa la descrizione; Vision deve essere abilitata sul modello scelto. |
| Immagine → ritocco → slide/infografica | Ritocca l'immagine salvata e inseriscila nella pagina scelta o nel nuovo artefatto. |
| Slide/infografica/trascrizione/calcolo → altra creazione | Riusa il testo, le note e i file dell'artefatto. |
| Musica/voce → Manim | Usa l'audio come colonna sonora e chiedilo esplicitamente nel compito. |
| Infografica → musica → infografica | Ricava la durata, genera il brano, applica la copia adattata e aggiorna il rendering. |
| Canzone → Re-sing → trascrizione/colonna sonora | Ricanta con nuovo testo conservando la melodia, poi usa l'audio salvato. |

La compatibilità riguarda i dati realmente utilizzabili, non tutte le conversioni
immaginabili. Un audio senza trascrizione non diventa testo e un'immagine senza
Vision non diventa una descrizione: lo strumento indica il passaggio mancante.
Per inserire un'immagine come asset grafico non occorre descriverla con Vision.
Non vengono interpretati movimenti o montati filmati. Il contenuto delle fonti
rimane un dato: non può modificare strumenti, istruzioni o autorizzazioni.
Vision usa una miniatura CPU fino a 768 pixel e 128 KiB, conserva l'originale e
dichiara i dettagli non leggibili; non è una verifica della fedeltà dell'immagine.

## Preparare un progetto RAG dal prompt

Attiva **Consenti creazione di progetti, importazione file e indicizzazione RAG**
nelle impostazioni Agent. Puoi scrivere, per esempio:

> agent: Prendi il PDF e le immagini allegate. Trova il progetto «Porte logiche»;
> se non esiste, crealo. Cataloga le immagini con il modello Vision configurato,
> copia tutti i file nel progetto e indicizzali con EmbeddingGemma 2, su CPU.
> Controlla quali fonti sono pronte prima di creare cinque slide dai contenuti.

Il dispositivo RAG segue quello scelto nelle impostazioni H3: il prompt non forza
un dispositivo diverso. Se vuoi CPU, selezionala prima del lancio. I modelli devono
essere già installati/collegati. `list_rag_models` espone il modello configurato e
gli embedding integrati disponibili, oltre alla ricerca lessicale. Non accetta
percorsi modello scritti dal LLM e non avvia download.

La catalogazione usa il modello chat Vision selezionato, oppure un `model_id`
Vision disponibile indicato esplicitamente. Salva una caption fino a 1.200 caratteri
per immagine, riutilizzabile nell'indice anche con un embedding soltanto testuale.
Ovis ed EmbeddingGemma 2 possono aggiungere anche embedding visivi quando richiesto.
Scegliere un embedding non equivale a scegliere il modello che descrive le immagini.

Importare e indicizzare sono due operazioni distinte. L'importazione fa una copia
privata nel progetto e conserva la caption; gli originali restano intatti. Il report
di indicizzazione indica le fonti pronte, gli errori e gli estratti effettivamente
salvati. I duplicati non aggiungono nuove fonti. Un progetto esistente non perde
nome, istruzioni o fonti; nomi ambigui richiedono un ID preciso.

Il progetto diventa il riferimento di quella sessione Agent; la chat mantiene la
sua collocazione. La scelta embedding è salvata nel checkpoint per le successive
ricerche del run e non cambia il modello RAG globale. Altre sessioni seguono le loro
impostazioni e possono ricostruire l'indice, come nel flusso ordinario di H3.
Per cercare i contenuti e usarli nelle creazioni attiva anche il pulsante RAG.

Sono esclusi motore generativo video, modifica video e timeline. I filmati prodotti
proceduralmente da Manim e dalle infografiche restano disponibili. Le infografiche
con video di sfondo non vengono modificate da Agent in questa versione.
Manim resta indisponibile nell'edizione macOS, come nel flusso ordinario.

Per le slide si acquisiscono gli ultimi preset salvati. Infografiche, voce, musica,
modelli e dispositivi riutilizzano le impostazioni H3, entro i permessi del run.
Il prompt esplicito prevale sulle preferenze supportate; non concede nuovi permessi.
Agent non afferma di aver visto un'immagine priva di analisi Vision. La misura dei
bordi delle slide non costituisce una revisione estetica né una garanzia di qualità.

## Controlli della sessione

Le impostazioni offrono passaggi massimi (1–50), tempo attivo (1–120 minuti),
chiamate LLM (1–500) e budget token prudenziale (8.000–2.000.000). Le chiamate
interne ai motori H3 sono incluse. Il budget riserva input UTF-8/schema e output
massimo richiesto: non è il numero di token fatturato, né un preventivo in euro.
La sessione avvia al massimo 50 immagini. Non si applicano prezzi inventati.

Immagini, generazione audio, Manim, trascrizione e gestione progetti hanno permessi distinti. Web e
Vision seguono i rispettivi controlli della chat/modello. RAG segue
il pulsante della chat e la sua selezione fonti. L'interruttore CPU mantiene i vincoli
ordinari: non viene aggirato per usare modelli multimediali. La generazione immagini
non viene attivata implicitamente creando slide; Agent può prima creare un lotto e
poi usarlo. L'infografica richiede permessi coerenti con voce, musica o immagini richieste.

**Chiedi conferma prima di creare o modificare** è attivo per impostazione iniziale.
In chat compare il passaggio concreto, con istruzioni, quantità e modello: Approva
esegue solo quel passaggio, Rifiuta ferma la sessione. Disattivando la conferma prima
del lancio si autorizzano i passaggi consentiti entro i limiti della sessione.
Skill, fonti e risultati non possono cambiare questi permessi.

## Stop, limiti e recupero

Stop interrompe il modello e gli strumenti in corso; non avvia altri passaggi.
Con **Riprendi Agent** si continua lo stesso run, conservando risultati e permessi.
Puoi aumentare i limiti nelle impostazioni Agent prima di riprendere. La ripresa
esplicita usa il LLM attualmente selezionato e i suoi parametri; le ricette degli
strumenti e le autorizzazioni della sessione rimangono quelle salvate.

Il checkpoint precede ogni azione. Le scritture identiche riutilizzano il risultato
registrato. Se un'azione viene interrotta o il suo esito resta incerto, non viene
rilanciata automaticamente. Apri il risultato parziale; **Continua dai risultati
parziali**, quando disponibile, ne riconosce esplicitamente la conservazione.
Agent potrà leggere la bozza e completare le parti mancanti, senza ripetere la
creazione originaria. Gli artefatti parziali e gli originali rimangono nel canvas.

Le attese di approvazione liberano la coda; non tengono il worker occupato.
Tutti i servizi usano la coda e il limite di calcolo condiviso di H3.
Ogni azione conserva un artefatto distinto, con accesso dalla risposta Agent.

## Esempi

> agent: Usa le fonti del progetto per preparare 10 slide sulle porte logiche.
> Riutilizza i lotti pertinenti, controlla i bordi e correggi le pagine problematiche.

> agent: Ritocca con Qwen l'immagine dell'artefatto indicato, schiarendo lo sfondo.
> Poi usa il risultato nella slide 3, conservando le altre pagine.

> agent: Crea un sottofondo strumentale per l'infografica salvata, adatto al suo
> tema e alla durata delle scene. Applicalo conservando la narrazione.

Per il secondo esempio abilita immagini; per il terzo abilita generazione audio.
Le conferme rimangono attive finché non scegli diversamente per il nuovo run.

## API e isolamento

`POST /api/chats/CHAT/messages` con `lab: "agent"`, prompt e opzioni `agent` avvia
il run. `agent_request_id` (32 cifre esadecimali) permette di riconciliare un invio
ripetuto dopo una risposta persa; il browser lo conserva finché il POST non riesce.
Lo stesso identificatore nella stessa chat non crea un secondo run.

`GET /api/chats/CHAT/agent-runs/RUN` restituisce lo stato pubblico.
`POST /api/chats/CHAT/agent-runs/RUN/resume` riprende o approva il passaggio esatto.
Le approvazioni richiedono `action_id` e `decision: "approve" | "reject"`.
Una ripresa ordinaria può fornire i nuovi `limits`; non può ampliare i permessi.
Il checkpoint è sotto `outputs/RUN/agent/`, nella cartella dati del relativo workspace.

Non esistono strumenti Agent per shell, query SQL, lettura delle credenziali,
installazioni o cartelle esterne. Gli URL Web devono essere pubblici; i download
immagini bloccano indirizzi privati e verificano ogni reindirizzamento, con DNS
vincolato all'indirizzo validato. Gli ID degli artefatti sono verificati sulla chat
e i lotti sul workspace. Gli strumenti richiamano i servizi esistenti attraverso
un registro finito, indipendentemente da ciò che il modello scrive nel prompt.

Il coordinatore iniziale è Python e usa il protocollo JSON dei modelli già supportati.
Non incorpora il runtime DeepSeek Harness. Un adattatore a quel runtime rimane una
valutazione successiva; questa scelta evita una seconda installazione Node/server.

## Catalogo e preset dei modelli

`list_model_catalog` distingue modelli disponibili, collegamenti locali/API e
modelli scaricabili dal catalogo verificato. `download_catalog_model` usa il gestore
H3 e i suoi SHA256: restituisce avvio/stato, senza caricare il modello o cambiare
il default. `model_download_status` verifica il progresso. I download sono lavori
separati del gestore H3 e restano visibili anche dopo la fine del run Agent.

`set_model_preset` salva solo parametri immagini/video ammessi dai validatori H3.
`make_default=false` lascia il modello opzionale. Non cambia il LLM, le credenziali
o le cartelle. Un modello nuovo non presente nel catalogo, o con un’architettura
non supportata, non può diventare compatibile semplicemente scaricandone il file:
serve prima un’integrazione del motore. Il controllo Globale permette lo sviluppo
locale autorizzato, ma non equivale a una compatibilità automaticamente verificata.
