# Caricamento dal PC

Chat, modifica clip, remix, upscale, immagini delle slide e progetti accettano file
di qualsiasi formato, senza un limite applicativo alla dimensione totale.
Anche i file senza estensione e i file vuoti possono essere conservati in galleria.
I file vengono trasferiti in blocchi da 2 MiB; il browser e il server non devono
caricare il file intero in memoria. Anche i download usano streaming e byte range.

Il caricamento conserva i byte originali. La compatibilità di un file viene
controllata dal motore che lo utilizza: un file salvato può non essere visualizzabile
nel browser o interpretabile dal modello. Nel RAG i formati non indicizzabili
rimangono nel progetto e in galleria, con un avviso sul documento.
I limiti di analisi (pagine, testo estratto, contesto del modello) restano separati
dal caricamento, così come i limiti al numero di riferimenti per richiesta.

I trasferimenti e i file sono privati per ogni area utente. I metadati e i
trasferimenti incompleti non sono scaricabili. HTML, script e altri contenuti
attivi vengono serviti con restrizioni di esecuzione. La disponibilità effettiva
dipende dallo spazio disco e dalle capacità del browser e del filesystem.

API: `POST /api/uploads/start` con `name`, `size` e `origin`; inviare i blocchi
base64 con `POST /api/uploads/{id}/chunk` e `offset`; completare con
`POST /api/uploads/{id}/finish` oppure annullare con `DELETE /api/uploads/{id}`.
L'API storica `/api/uploads` rimane compatibile per i piccoli trasferimenti JSON.
