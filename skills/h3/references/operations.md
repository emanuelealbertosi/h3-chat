# Operazioni, API e sviluppo

## Accesso e stato

- Root locale: la cartella individuata dagli helper (`--root` o `H3_CHAT_ROOT`, poi skill inclusa/progetto corrente). Non assumere un percorso globale. Porta effettiva in `<root>/data/port.json`; non fissare 8788 per sempre.
- `scripts/status.py --job ID` usa il solo percorso locale e la manutenzione già disponibile. Non stampa credenziali né prompt di altre chat. Può leggere il checkpoint anche con server spento.
- `scripts/api_client.py` offre un `Client(root)` contestuale per le API locali dell'owner: apre una sessione temporanea con le classi Access esistenti, la rimuove all'uscita, non costruisce Service/Store. Usa le mutazioni solo entro la richiesta autorizzata; l'helper non è un'autorizzazione. Non stampare cookie, CSRF o maintenance token.
- Per un account diverso dall'owner usa la sessione autenticata corretta, non assumere che tutti i workspace siano quello dell'owner.
- La base delle route è `/api`; `Client.call` riceve `/state`, `/chats/...`, eccetera, senza ripetere `/api`.
- Scopri gli schemi della versione installata in `app.py` e nel relativo modulo di `h3chat`. Per i controlli UI il payload reale è nel modulo `ui/` corrispondente. Non inventare endpoint da nomi plausibili.
- `data/chat.sqlite` è il database owner; altri workspace hanno dati separati. SQLite: `sqlite3.connect((root/'data/chat.sqlite').as_uri()+'?mode=ro', uri=True)`, con `root` assoluto. Prima di interrogare tabelle sconosciute leggi `PRAGMA table_info`; filtra per ID noto ed evita dump di tutti i messaggi.

## Invii e lavori lunghi

Prima di POST: salva richiesta esatta, preflight e identificatore della chat in una cartella `work/NOME-DATA`. Registra `uncertain_submission` PRIMA dell'invio; al successo scrivi il `job_id`. Una risposta persa non autorizza un altro POST. Cerca il lavoro reale in sola lettura prima di decidere. Conserva un solo controller per richiesta.

Il checkpoint video `data/outputs/JOB/scenes.json` conserva timeline, output, ricette e revisioni. Il suo avanzamento può arrivare dopo i log. Un errore del controller non prova un errore del motore. Rispetta cancellazioni intenzionali e istruzioni di non rilancio.

Un monitor ricorrente richiede la richiesta dell'utente e gli strumenti automazioni di Codex: usa quelli disponibili, non un cron improvvisato. Deve osservare un job esatto, restare silenzioso senza cambiamenti utili, evitare nuovi invii e disattivarsi quando l'esito è stato presentato. Salva un marcatore di presentazione per evitare doppioni.

## Sviluppo, build e attivazione

Leggi `docs/build.md`, `package.json`, i test del modulo e il diff corrente. Il repo può contenere modifiche non ancora pubblicate: non ripristinare file interi. Per il codice raggiungi prima `rg` e usa percorsi reali con `-g`; PowerShell non espande i glob nei percorsi come una shell Unix.

Python: `<root>/runtime/python/python.exe -X utf8`. Strumenti CPU immagini/video: librerie in `<root>/runtime/tools/documents`; individua FFmpeg/FFprobe nella configurazione dell'app e nel PATH effettivo, senza assumere un disco. Per test temporanei usa una cartella dedicata consentita dall'ambiente se il sandbox Windows impedisce Temp. Non usare il DB reale nei test: fixtures isolate.

La build UI genera `static/app.js`; distribuzione/bootstrap seguono `docs/build.md`. Verifica i controlli interessati e i test appropriati, poi attiva con riavvio solo a coda globale libera e solo se autorizzato. Non riavviare app/motori mentre generano. Non fare push, release o cancellazione pesi per il solo fatto di aver cambiato codice.

Una modifica API/UI non va dichiarata funzionante per sempre: distingue test isolati, browser, attivazione verificata e prova reale del modello. Mantieni documentazione e stato coerenti.
