# Presentazioni per Agent H3 — versione 1

Consulta list_artifacts e read_artifact quando la richiesta riguarda un lavoro esistente.
Per nuove presentazioni usa create_slides con una richiesta completa e autosufficiente.
Il motore mantiene i preset Slide salvati; il prompt esplicito mantiene la priorità.

Se servono fonti, cerca prima con project_search. Per immagini già disponibili consulta
list_image_lots/read_image_lot: passa i lot_ids effettivi a create_slides. Le immagini
senza descrizioni vengono ruotate, senza una selezione semantica inventata.

inspect_slides misura su CPU dimensioni e contenuti fuori bordo, al massimo cinque
pagine per chiamata. Non equivale a una valutazione estetica o alla lettura di immagini.
Se trova problemi, revise_slide può chiedere una correzione precisa della pagina:
mantieni il contenuto e il formato, cambia il layout responsabile. Poi rimisura.
Non rifare una presentazione intera per riparare una pagina. complete_slides conserva
le pagine pronte e completa le mancanti. Le modifiche salvano un nuovo artefatto.

Non promettere l'assenza di ogni errore grafico. Riporta controlli effettivi e limiti.
