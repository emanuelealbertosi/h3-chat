# Account e accesso remoto

Apri **Accessi** nella barra superiore, oppure `http://127.0.0.1:8788/access`
(usa la porta indicata nei log se diversa). Il primo amministratore si configura
dal PC che ospita l’app: nome utente e password di almeno 12 caratteri.
Finché manca questo account, l’accesso locale funziona e quello remoto è bloccato.
Dopo la configurazione, anche il browser locale richiede il login.

Le chat, i documenti e il RAG esistenti restano nel tuo spazio amministratore.
Da **Accessi → Ospiti** crea un account per ogni persona. Ogni ospite dispone di
una cartella `data/workspaces/<id>` con database, progetti, indice, allegati,
canvas, esportazioni e risultati propri. I file degli altri utenti non vengono
copiati né serviti al suo browser. I documenti si caricano dal dispositivo
dell’ospite tramite selettore o trascinamento; i percorsi del server, i modelli,
i provider e l’installazione dei motori si gestiscono soltanto da amministratore.
La scelta LLM e Vision in chat e la scelta CPU/GPU del RAG sono personali.

I collegamenti ai modelli e ai provider configurati dall’amministratore vengono
riutilizzati nelle aree ospite. Le credenziali dei provider restano sul server.
Le generazioni e l’indicizzazione GPU usano lo stesso blocco di calcolo: quando
un altro utente sta usando il motore, il lavoro mostra **Attesa motore**. I pesi
dell’altra area vengono rilasciati prima del caricamento successivo.

Per l’accesso remoto resta necessario Tailscale: condividi il dispositivo con
la persona e forniscile il suo account ospite, non le credenziali amministratore.
Non vengono attivati Funnel o porte pubbliche sul router.

## Password, sessioni e chiavi

Le password sono conservate come hash PBKDF2-HMAC-SHA256 con salt casuale e
600.000 iterazioni. Le sessioni durano 12 ore, usano cookie HttpOnly/SameSite
Strict e Secure sul collegamento HTTPS; le modifiche dal browser richiedono
anche un token CSRF distinto per sessione. Login errati ripetuti vengono limitati.

In **Chiavi di accesso** puoi creare una chiave per il tuo account o, se sei
amministratore, per uno degli ospiti. La chiave viene mostrata una volta sola,
è conservata come hash e scade dopo 7, 30 o 90 giorni. Può essere incollata nel
login, oppure inviata alle API nell’header `Authorization: Bearer CHIAVE`.
Non inserirla nell’indirizzo del browser. Le API con chiave conservano gli stessi
permessi e la stessa area dell’account associato.

**Revoca accesso** disabilita l’ospite, revoca sessioni e chiavi e interrompe il
suo motore; conserva i suoi documenti. Riattivandolo, serve la password oppure
una nuova chiave. Cambiare password revoca le sessioni e le chiavi dell’account.

Avvio, arresto e aggiornamento locali continuano a funzionare senza una sessione
browser, con una credenziale di manutenzione locale separata: consente soltanto
il controllo dei lavori attivi, l’arresto e la configurazione Tailscale. Non dà
accesso a chat o documenti e non viene accettata da richieste proxy Tailscale.

## Recuperare la password amministratore

Se hai perso la password, arresta l’app dal PC e usa:

```powershell
runtime\python\python.exe -X utf8 scripts\reset_admin_password.py
```

Inserisci la nuova password nel terminale: non appare sullo schermo e non viene
passata come argomento. Il comando conserva tutti i dati e revoca le sessioni
e le chiavi dell’amministratore. Poi riavvia H3-Chat e accedi normalmente.
