# Lavori, recupero e riepilogo

Il pulsante **Lavori** in alto raccoglie le ultime richieste e i download
disponibili per l'account corrente. I filtri sono In corso, Da controllare e
Tutti. Sono mostrati la fase comunicata dal motore, il tempo dall'invio
(inclusa la coda) e i byte dei download quando disponibili. Non vengono
inventate percentuali o tempi residui per le generazioni.

Le azioni aprono la chat, l'artefatto associato o una bozza della richiesta.
Interrompi usa i comandi esistenti per quel singolo lavoro. Ricarica richiesta
non invia una nuova generazione. Per completare slide o schede parziali aprire
Risultati salvati e usare il comando di completamento del rispettivo editor.
Per i download interrotti, Apri installazione permette di usare i comandi già
disponibili del componente. Il pannello non mostra lavori di altri account.

Sotto il prompt, **Riepilogo** mostra modello richiesto, formato, parametri,
allegati, destinazione, LoRA e selezione RAG. Zero fonti selezionate è distinto
da tutte le fonti. La consultazione non cambia le impostazioni e non aggiunge
una conferma obbligatoria. Sono i valori della bozza: le istruzioni nel prompt
prevalgono e il percorso Automatico viene risolto dopo l'invio. Nella modalità
Sfondi è esplicitato che allegati e RAG non vengono utilizzati.

Gli errori dei messaggi hanno comandi di recupero accanto al risultato; i dettagli
originali restano consultabili. Un'interruzione volontaria non è etichettata
come errore. Nessun rilancio automatico viene introdotto.

# Comandi del canvas

In **Modifica grafica** di slide HTML e locandine:

- Ctrl+Z annulla; Ctrl+Y o Ctrl+Shift+Z ripristina. Su Mac usare Cmd.
- Copia/Incolla e Ctrl+C/Ctrl+V duplicano un elemento o un gruppo, incluse le
  immagini. Un'immagine PNG, JPEG o WebP negli appunti può essere caricata e
  inserita; diventa un allegato locale del documento.
- Porta avanti/indietro cambia un livello. Primo piano/sfondo raggiunge gli
  estremi del gruppo corrente. Seleziona gruppo permette di operare sul gruppo.
- Applica e salva conserva le modifiche nel canvas. La cronologia della pagina
  resta disponibile durante la sessione anche dopo questo salvataggio; non è
  una cronologia permanente recuperabile dopo la chiusura dell'app.

Le scorciatoie nei campi di testo mantengono il comportamento del browser.
Annulla/ripristina da tastiera usa anche le cronologie esistenti dell'editor
classico e di Motion Graphics. Video già renderizzati, immagini raster singole
e PDF non vengono trasformati automaticamente in documenti a livelli.

# Esportazione PowerPoint

I nomi dei file distinguono ora `- modificabile.pptx` da `- fedele.pptx`.
Gli oggetti di testo e le immagini delle locandine hanno nomi riconoscibili nel
riquadro di selezione di PowerPoint. Le parole già disegnate dentro una foto
restano pixel: l'esportazione non esegue OCR o ricostruzione generativa.
