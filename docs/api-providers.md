# LLM tramite provider API

Apri **Impostazioni → Setup → LLM tramite API** (anche in Catalogo e Preferenze).
Scegli DeepSeek, OpenRouter oppure Personalizzato. Inserisci nome, indirizzo base,
chiave e ID modello; puoi caricare l’elenco dal servizio oppure scriverlo manualmente.
**Salva collegamento API** registra il modello senza cambiare quello attivo.
**Usa in chat** lo seleziona e salva le impostazioni presenti nella finestra.
Puoi mantenere più collegamenti, anche a modelli diversi dello stesso provider.

La chat mostra **API** accanto al nome del modello. Chat, router, preparazione prompt
immagini, stile/testo musicale e piano video riutilizzano questo LLM. Nessun peso
LLM viene caricato sul PC. Immagini, musica e video possono usare motori locali
o [server esterni](external-servers.md); Whisper resta sul PC. Assistant Off
conserva il percorso diretto ai generatori.
La modalità Residenti riguarda solo i processi locali: non genera richieste API
di precaricamento. A richiesta libera il precedente LLM locale quando si passa
alla chiamata API.

## Indirizzo, protocolli e chiavi

Supportato il protocollo **Chat Completions compatibile**: POST
`<base_url>/chat/completions`, Bearer token, risposta JSON o streaming SSE, GET
`<base_url>/models` per l’elenco. Per esempio, un server compatibile sul PC può
usare `http://127.0.0.1:1234/v1` oppure un IP privato LAN; i servizi Internet
devono usare HTTPS.
Puoi incollare anche l’indirizzo completo che termina in `/chat/completions`:
l’app ricava la base. Non aggiunge automaticamente `/v1` ad altri percorsi.
Le API native Anthropic Messages, Gemini GenerateContent e Responses non sono
implementate: usa un endpoint Chat Completions compatibile, quando disponibile.

Le chiavi sono protette da **Windows DPAPI**, legate al tuo utente Windows,
e conservate nella tabella privata `api_providers` di `data/chat.sqlite`.
Non vengono restituite allo stato UI, salvate nei messaggi/job o stampate nei log.
In modifica, un campo chiave vuoto conserva quella esistente; Rimuovi chiave la
elimina. Se cambi l’indirizzo devi reinserirla o rimuoverla. Su un altro PC/utente
va inserita di nuovo. I redirect API sono rifiutati, senza inoltrare credenziali.
Nessuna chiave, chat o configurazione personale entra nello ZIP o in GitHub.

Il provider riceve conversazione, istruzioni, estratti web/documenti, trascrizioni
e immagini effettivamente fornite a Vision/Assistant. I file PDF/Word completi
non vengono caricati con una Files API: vengono estratti sul PC. Gli audio
riferimento Video restano locali o vengono inviati al server video configurato;
la preparazione LLM API ne vede i nomi e le istruzioni, non dichiara di ascoltarli. Attivare API richiede Internet e può
consumare credito secondo le condizioni del servizio.

## Compatibilità del modello

Configura Vision e numero massimo riferimenti solo se il modello accetta immagini
base64. Vision Off blocca le richieste di analisi visiva e non invia immagini.
Nel percorso API non esiste un mmproj locale. Le pagine PDF rasterizzate seguono
la stessa scelta Vision e lo stesso limite riferimenti della chat.

Router, Assistant e canvas richiedono JSON. Default **JSON object** con schema
aggiunto alle istruzioni; **JSON schema** usa response_format strict se supportato.
**Solo prompt** evita il parametro response_format per servizi incompatibili.
La risposta viene comunque validata prima dell’uso. Un risultato non conforme
produce un errore, non istruzioni operative inventate o una richiesta automatica
a pagamento. L’app non ripete automaticamente le chiamate fallite.

DeepSeek usa thinking enabled/disabled e reasoning_effort:
Off → none, Low → low, Med/High → high, Xhigh → max. OpenRouter traduce Med
in medium e passa gli altri livelli come reasoning effort. Il terzo modo usa
reasoning_effort compatibile; Non configurato non invia parametri thinking.
Il modello può ignorare o rifiutare livelli non supportati. Router e Assistant
disattivano thinking; la risposta chat usa il livello selezionato. L’app mostra
l’attività di thinking, senza memorizzare il testo di ragionamento restituito.

Max token e temperatura si conservano per ciascun collegamento. La temperatura
non viene inviata quando è attivo un modo thinking. Il campo Contesto aiuta a
dimensionare estratti e risposte; non modifica il limite del servizio e non alloca
una KV cache locale. MTP/layer GPU sono disabilitati per modelli API.

**Prova connessione e modello** invia soltanto “Reply with OK.”, con 64 token,
senza chat o allegati; può consumare credito. Il servizio deve completare la
risposta entro il limite previsto. Errori di autenticazione, credito, parametri,
stream incompleto e annullamento vengono mostrati nella stessa chat/finestra.

Riferimenti ufficiali utilizzati: [DeepSeek Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/),
[DeepSeek JSON Output](https://api-docs.deepseek.com/guides/json_mode/),
[OpenRouter Chat Completions](https://openrouter.ai/docs/api/api-reference/chat/create-a-chat-completion).
