# Browser, Web e download nell’Agente

In Preferenze Agente, **Browser interattivo privato** abilita pagine dinamiche,
pulsanti, campi ordinari, menu, schede, schermate e download. Il browser usa un
profilo proprio del lavoro: non legge cookie, password o schede personali.
Richiede anche Web. Non controlla il desktop.

**Web quando serve** è attivo per impostazione iniziale. Se un passaggio richiede
Internet e Web è spento, compare una conferma per quello stesso passaggio. Dopo
l’approvazione il lavoro continua. Con Autoapprova autorizzato, Web viene abilitato
per il solo lavoro; le preferenze globali e gli altri permessi non cambiano.
Una richiesta esplicita di lavorare senza Internet viene rispettata.

Per un video YouTube l’Agente può usare `download_online_video`, con audio e limite
di risoluzione/dimensione. Un URL con parametri playlist rimane il singolo video
richiesto. Il componente privato yt-dlp/EJS viene installato da pacchetti con hash
verificati; Node e FFmpeg vengono risolti localmente o installati dai componenti
verificati previsti. Non vengono usati cookie personali né avviate generazioni GPU.
Eventuali limiti di accesso del sito sono riportati come errori reali.

Per file diretti, LoRA, fonti e immagini, l’Agente continua a preferire i tool H3
dedicati. Se manca un tool e la modalità Sandbox/Globale lo consente, può scrivere
ed eseguire codice nella cartella autorizzata, verificare dipendenze e correggere
errori concreti. Una semplice lista di capacità non dimostra che il compito sia
stato tentato o completato.

I riferimenti agli elementi del browser valgono per la relativa osservazione.
Dopo un’azione si osserva nuovamente. Esiti incerti, Stop e rifiuti non autorizzano
nuovi invii. Stop chiude anche i processi del browser privato. Il browser inattivo
scade dopo 15 minuti; screenshot e download completati restano negli output.

Limiti attuali: Internet pubblico HTTP/HTTPS, cinque schede, 128 MiB per download
del browser. Il downloader YouTube segue invece il limite delle Preferenze Agente.
Non sono supportati caricamenti di file, password, codici monouso o pagamenti dal
browser Agent. Le schermate vanno poi analizzate con Vision: salvarle non equivale
a ispezionarle.
