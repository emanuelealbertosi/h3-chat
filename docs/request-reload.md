# Ricarica richiesta

«Ricarica richiesta» sotto una risposta, oppure «Riutilizza» sotto il messaggio
originale, recupera la ricetta salvata nel lavoro senza avviarlo. Il prompt e gli
allegati tornano modificabili. La destinazione chat/canvas, Assistant, Web, RAG,
fonti selezionate, numero di estratti, LoRA e controlli delle modalità vengono
riapplicati. Una selezione RAG vuota rimane vuota.

Slide: numero/durata/timeout, motore, layout, animazione, Vision, colori, tono dei
testi, immagini, lotti e raccolte sfondi. Infografica: regia, scena, voce, musica,
effetti, sprite, video, tipografia e sfondi. Si recuperano anche locandine, Studio,
Voice, Musica/Re-sing, immagini, video, trascrizione, Manim e codice dell'interprete.
I lotti di soli sfondi tornano nella loro modalità; quelli immagini mantengono
nome, quantità e formato in un pannello modificabile. Le operazioni Upscale,
Remix e Ricrea video riaprono la propria finestra con i parametri salvati.

Modello LLM e parametri tecnici/generativi vengono conservati nella bozza della
chat e inviati come request_settings. Non modificano i predefiniti salvati.
«Usa impostazioni attuali» rimuove questa copia. I parametri sono validati come
quelli normali; la modalità CPU/GPU dell'installazione e i permessi dell'Agente
restano sotto il controllo attuale dell'utente. Token API e credenziali non fanno
parte della ricetta. Cambiare un collegamento API non ripristina le vecchie chiavi.

Le impostazioni originali devono essere ancora presenti nel database. Parametri
non registrati da versioni vecchie non possono essere ricostruiti. I riferimenti a
modelli, file, lotti o fonti eliminati non scaricano o sostituiscono nulla in modo
automatico: occorre scegliere riferimenti disponibili. Un seed originariamente
casuale rimane casuale; per fissare quello effettivo usa il recupero seed.
