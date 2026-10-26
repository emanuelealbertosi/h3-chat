# Agent: H3, Sandbox e Globale

Implementazione sperimentale del 26 ottobre 2026. Le verifiche e l’attivazione
locale sono registrate in `work/agent-computer-2026-10-26`. I pulsanti compaiono
sotto le modalità del prompt quando scegli Agent. Assistant resta separato.

## Le tre scelte

- **H3**: strumenti dell’app, Web pubblico, documenti, RAG, progetti, lotti,
  immagini, voce, musica, infografica, Manim, slide e video/timeline. Rispetta i
  permessi delle Impostazioni Agent, incluso allow_video separato, e la modalità
  CPU/GPU. Nessuna shell o lettura libera del disco.
- **Sandbox**: strumenti H3 più file e programmi nella cartella scelta. Il
  proprietario locale sceglie una cartella reale separata dall’app; deve essere
  priva di junction, symlink e file con hard link. Il modello non può sceglierla
  o concedersi il permesso. L’esecuzione è un processo Windows LPAC con accesso
  a quella cartella e al runtime Python in sola lettura. Python, cmd e programmi
  compatibili nella cartella funzionano. Windows PowerShell 5 richiede COM e
  non è ammesso con questo isolamento: usa Python/cmd o Globale.
- **Globale**: strumenti H3, percorsi assoluti e programmi del PC con i privilegi
  ordinari dell’utente. Mostra un avviso esplicito su lettura, modifica,
  cancellazione, esecuzione e invio dei contenuti al modello scelto. Richiede
  consenso locale; non è una protezione della cartella o dei dati dell’utente.

Sandbox e Globale sono disponibili per ora su Windows. Su Mac gli strumenti H3
restano disponibili; nessuna esecuzione non isolata sostituisce silenziosamente
un confine non supportato. Al caricamento della pagina la scelta torna H3:
le autorizzazioni al PC non vengono ripristinate da localStorage.

Sandbox ammette Internet pubblico e la capability Windows `registryRead` per
le impostazioni di avvio, autorizzata espressamente dall’utente. Non concede
COM, scrittura del registro, LAN/loopback o accesso ai dati privati H3. Il runtime
in sola lettura e le risorse di sistema necessarie restano visibili: non è una
macchina virtuale. I file letti possono raggiungere il provider LLM scelto.

## File, codice e collegamento con H3

`computer_files` elenca, legge, cerca, crea, sostituisce, copia, sposta e rimuove
file. In Sandbox i percorsi sono relativi; in Globale sono assoluti. La
sovrascrittura richiede l’hash SHA256 dell’ultima lettura e conserva una copia
`.h3-backup-*`. Le eliminazioni di cartelle non sono ricorsive. Con codice
arbitrario autorizzato l’agente può fare operazioni più ampie nel proprio
perimetro: il limite di sicurezza è il token Windows, non una lista di parole
proibite. Non si deve presentare il controllo hash come protezione da codice
al quale si è già concesso pieno accesso alla cartella.

`computer_run` esegue il programma senza importarlo nel processo H3. Restituisce
exit code e uscita reale, massimo 32.000 byte in osservazione; oltre 4 MiB di
uscita il programma viene fermato. Ogni comando ha un timeout fino a 600 secondi,
un Job Object che termina i discendenti, limite di 32 processi e 8 GiB di memoria.
Le variabili con chiavi/provider non vengono ereditate. Un risultato precedente
non viene spacciato per nuovo test dopo una modifica dei sorgenti.

`import_computer_file` e `export_computer_file` copiano fino a 20 MiB fra il
perimetro autorizzato e gli artefatti H3 della chat. I byte passano dal broker,
non vengono inclusi nel prompt o nel checkpoint come Base64. Dopo l’importazione
occorre leggere/analizzare il file con lo strumento pertinente; non si inventa
il suo contenuto. L’esportazione non sovrascrive una destinazione esistente.

Stop termina anche i processi figli. Tornare a H3 revoca il consenso e cancella
soltanto i run che usano quel consenso, senza fermare lavori di altri utenti o
run indipendenti. Il file di consenso è tenuto fuori dalla cartella scelta;
lo stato del modello non può crearne uno. Una ripresa non amplia il perimetro.
Una scrittura interrotta conserva esito incerto e non viene ripetuta alla cieca.

## Amministratore e UAC

Solo in Globale, `request_admin` prepara un comando PowerShell concreto e il
motivo. Agent rilascia la coda e mostra una finestra H3 con il comando completo.
L’utente può rifiutare, chiudere per ora, oppure approvare e chiedere UAC.
Solo dopo l’approvazione parte un helper distinto tramite `ShellExecuteEx/runas`:
la finestra nativa di Windows deve essere approvata dalla persona.

L’helper elevato esegue un solo comando, con timeout e Job Object propri. Perde
il collegamento col processo H3 quando arriva Stop o il controller muore e
termina i figli. Non eleva il server H3 e non conserva un terminale amministratore.
Una conferma UAC rifiutata termina il run; nessun rilancio automatico. La richiesta
è riservata al proprietario nel browser locale, non a guest, sessioni remote,
proxy o chiavi API. I test automatici non hanno aperto o accettato UAC reale.

## Esempi

In H3:

> agent: Crea una presentazione sulla macchina di Turing di 5 slide. Cerca fonti
> primarie su Internet, scarica i documenti originali e le immagini utili, e cita
> le fonti nella presentazione.

La composizione ricerca → documento originale → lettura → immagini → lotto →
cinque slide è verificata con provider simulati e i veri builder H3. Non misura
la qualità o l’autonomia di uno specifico LLM su Internet reale.

In Sandbox:

> agent: Crea un programma Python in questa cartella, scrivi le istruzioni,
> eseguilo e correggi gli errori finché il test passa.

Usa il tool H3 quando disponibile, dichiarando quale: una presentazione o un PDF
non vanno prodotti aggirando il motore H3 con uno script inventato.

## Limiti rispetto a DeepSeek Harness

Sono strumenti nativi del coordinatore H3, non l’installazione completa di
DeepSeek Harness. Browser grafico con login/JavaScript, mouse/tastiera, LSP,
plugin arbitrari, terminali persistenti e sottoagenti sono fasi separate. Il Web
attuale cerca e legge pagine pubbliche e scarica file: non promette superamento
di CAPTCHA o accesso a sessioni già aperte.

Fonti: [Microsoft LPAC](https://learn.microsoft.com/en-us/windows/win32/secauthz/implementing-an-appcontainer),
[Microsoft UAC/runas](https://learn.microsoft.com/en-us/windows/win32/shell/launch),
[DeepSeek tool catalog](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/tool-catalog.md).
