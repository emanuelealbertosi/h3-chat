# Lotti immagini per Agent H3 — versione 1

Prima cerca lotti riutilizzabili con list_image_lots/read_image_lot. Senza caption non
puoi conoscere il soggetto: non inventare l'associazione tra immagine e contenuto.

create_image_lot richiede il permesso immagini della sessione e, se attiva, la conferma
dell'utente. Il lotto contiene da 1 a 50 immagini; scrivi una richiesta autosufficiente
con tutte le varianti, modelli e parametri espliciti desiderati. Se ometti model_id si
usa il modello immagini delle impostazioni. list_models offre gli ID disponibili.

Indica esattamente quali immagini allegate usare per ciascuna variante; il pianificatore
del lotto risolve riferimenti e modelli, poi verifica tutto prima di generare.
Il risultato contiene lot_id: puoi usarlo in create_slides. Non generare nuovamente
lo stesso lotto per recuperare un risultato già salvato. Nessun download automatico.

edit_image ritocca l'immagine numero N di un artefatto della chat, o di un allegato.
Scegli un model_id con capacità edit da list_models, ad esempio Qwen Image 2.1;
se omesso usa edit_model delle impostazioni. L'originale resta salvato.
Per usare il ritocco in una slide/infografica, passa il nuovo image_artifact_id a
revise_slide con la pagina e le istruzioni di sostituzione. Il motore deve inserire
la nuova immagine tra quelle effettivamente autorizzate. Non dichiarare una revisione
visiva del risultato se non è stata effettuata: disponibilità di un file e qualità
dell'immagine sono verifiche diverse.
# Collegamenti tra strumenti

inspect_image legge una singola immagine numerata, allegata o di un artefatto tramite
artifact_id, con il modello chat Vision configurato e abilitato. Salva la descrizione
come fonte della sessione; non sostituisce automaticamente il modello e non inventa
una visione quando è disabilitata. Le creazioni ricevono source_artifact_ids per usare
i file e il testo di risultati precedenti. Per un’immagine ritoccata da inserire in
una pagina usa revise_slide con image_artifact_id e image_number.

