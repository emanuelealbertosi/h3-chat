# Finestre di impostazione

Le modali condividono dimensioni ampie: circa il 72% della larghezza e l’86%
dell’altezza dello schermo, con un minimo di larghezza utile sui desktop e
adattamento quasi completo allo schermo sui telefoni. Intestazioni, schede e
pulsanti di conferma restano raggiungibili nelle finestre strutturate mentre
il contenuto scorre. Gli editor multimediali conservano i propri controlli.

Campi, tendine, aree di testo e pulsanti hanno dimensioni e spaziature coerenti.
Le scelte non vengono ricreate o azzerate aprendo e chiudendo la finestra.
Studio distingue tipo di documento, quantità e livello, testo fonte e voci;
queste ultime sono visibili soltanto per i dialoghi.

Il **Primo avvio** è diviso in quattro passi: tipo di utilizzo (locale, API o
misto), computer, modelli e memoria/installazioni. L'hardware viene rilevato;
la configurazione proposta si applica alla bozza soltanto premendo il pulsante.
Non vengono avviati download in automatico.

**Modelli e installazioni**, raggiungibile anche dalla barra laterale, è il
punto comune per catalogo generativo, collegamenti ai file esistenti, motori,
componenti, modelli RAG/trascrizione e avanzamento. Ricerca e filtro limitano la
lista visibile. I vecchi pulsanti contestuali rimandano qui. La verifica di
compatibilità usa i parametri correnti per una stima, senza cambiare le scelte.
Su Mac i runtime compatibili si aggiornano con il pacchetto dell'app.

Le **Preferenze** mostrano un argomento alla volta, con una navigazione laterale
(orizzontale sugli schermi piccoli). I gruppi lunghi hanno sottosezioni e i
testi di aiuto estesi sono espandibili. Slide, locandine e infografiche raggruppano
i controlli per funzione; i preset restano raggiungibili. Anche Agente e Crea
sfondi dividono budget/permessi e tema/composizione/qualità in schede separate.
Tutti i campi mantengono valori e gestori originali, anche quando sono nascosti.
La validazione porta alla sezione del campo da correggere.

Lo stile condiviso è in `static/dialogs.css`. Il controllo browser copre le
modali native già presenti, la griglia Studio, il mantenimento dei valori,
desktop e schermo stretto. I percorsi di video, MOSS e Studio sono verificati
separatamente per le rispettive azioni.

`tests/browser-settings-center.mjs` controlla guida hardware, inventario, ricerca,
download/annullamento simulati, compatibilità, bozze tra sezioni e schede delle
modalità. Non scarica pesi e non avvia inferenze. I test di preset slide e sfondi,
Qwen Turbo e installazione API verificano le rispettive regressioni.
