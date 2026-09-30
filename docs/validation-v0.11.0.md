# Verifiche H3-Chat 0.11.0

Collaudo Windows x64, Python privato 3.13, dati temporanei separati dalle chat
personali. Nessun peso copiato da cartelle esterne; nessun motore cloud.

- **141 test Python e 2 JavaScript**: regressioni chat/immagini/musica/video,
  documenti reali, PDF protetti, limiti ZIP/documenti, rasterizzazione pagine,
  limite vision, indici di pagina, estratti e numeri non spezzati, fonti web,
  URL privati/redirect, errori e annullamento, snapshot delle impostazioni,
  precedenza del pulsante Trascrivi, assenza di LLM nella sola trascrizione,
  TXT/SRT, canvas e stato del runtime dopo installazione completa.
- **Whisper Tiny reale**, CPU INT8: audio inglese sintetico di circa 10 s,
  1200 euro di ricavi / 900 euro di profitto e orario riconosciuti. Trascrizione,
  TXT e SRT completati in circa 1,2 s incluso l’avvio; nessun processo LLM.
- **Whisper Small reale**, CPU INT8: parlato italiano sintetico, lingua rilevata
  automaticamente come italiano; orario e valori 1200 / 900 riconosciuti.
  Output nel canvas e TXT/SRT completati in circa 5,7 s incluso il caricamento;
  processo e modello liberati. Questi brevi audio non rappresentano un benchmark
  di registrazioni lunghe, rumorose o con più parlanti.
- **PDF/Word con LLM reale Qwen3 0.6B CPU**: estrazione di testo e tabella,
  risposte con ricavi 1200 / profitto 900, nessun input vision per documenti
  testuali. Il piccolo modello non cita sempre la pagina nel testo: l’app
  conserva e mostra comunque i riferimenti dei passaggi forniti.
- **Ricerca online reale**: DuckDuckGo ha recuperato documentazione pypdf,
  pagine Read the Docs lette, URL reali conservati; una pagina PyPI con challenge
  è stata marcata come solo estratto. Verificato anche il percorso fino a una
  risposta del LLM con fonti aggiunte dall’app. Risultati Bing estranei alla
  richiesta vengono scartati. Non certifica ogni query o provider.
- **Interfaccia Chrome headless**: upload PDF e Word nella stessa chat,
  etichette Documento 1/2, Web, esclusione Trascrivi/Video, selezione di una
  cartella modello tramite browser FS, salvataggio di thread e fonti, riapertura
  delle preferenze, trascrizione reale dal composer e due link TXT/SRT. Nessun
  errore JavaScript; schermate verificate visivamente.
- **Portabilità**: librerie Microsoft verificate installate accanto ai pacchetti
  privati; MSVCP del motore ASR caricata dalla directory dell’app, non da System32.
  I worker mantengono deadline e annullamento; un processo attivo è stato fermato
  durante il test. Runtime e modelli usano file/revisioni/hash fissati.
- **ZIP da cartella nuova**: manifest SHA-256 verificato per tutti i 915 file,
  avvio dei worker, stato dell’app, lettura reale PDF/Word con Python e librerie
  inclusi. Nessuna chat, preferenza personale o peso modello nel pacchetto.

Le prove del servizio usano mock per il LLM e l’ASR dove indicato nei test;
le inferenze e le ricerche descritte sopra sono reali. Il test vision controlla
rasterizzazione, assegnazione e limiti delle pagine; non misura la precisione
OCR del modello. Analisi generale dei suoni e diarizzazione non sono implementate.
