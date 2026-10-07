# Animare una presentazione con Manim

Seleziona **Manim**. Il pulsante **Anima presentazione** si abilita quando
hai allegato PDF, PowerPoint **PPTX** o immagini, oppure quando il canvas
contiene una presentazione completata. Un file audio o Word da solo non
abilita questa funzione. Il normale Manim libero continua a funzionare.

Attiva il pulsante e scegli la sorgente: **Allegati** oppure **Slide nel canvas**.
Le slide del canvas vengono esportate internamente in PDF, comprese immagini,
font e modifiche grafiche, senza avviare un download. Quando rimuovi tutte le
sorgenti disponibili, l’opzione si disattiva. La sorgente della richiesta viene
conservata negli allegati per la rigenerazione, anche se il canvas poi cambia.

Sono disponibili due modalità:

- **Mantieni layout**, predefinita all’attivazione: il renderer mantiene la
  pagina originale come sfondo e il LLM scrive il Python Manim per animare
  evidenziazioni, puntatori, dettagli ingranditi e spiegazioni sovrapposte.
  Non separa automaticamente tutti gli oggetti di una fotografia della slide.
- **Ricostruisci con Manim**: il LLM riceve testi, posizioni misurate, anteprima
  quando Vision è attiva, e ritagli delle immagini originali. Ricrea oggetti,
  formule e diagrammi animabili. Font ed effetti possono differire dall’originale.

Una scena viene prodotta per ciascuna slide, mantenendo l’ordine del PDF,
del PPTX o degli allegati immagine. Le immagini non vengono rigenerate.
Le proporzioni sono conservate; pagine con formati diversi vengono adattate
senza deformazione. Se nel prompt specifichi una durata, viene ripartita fra
le slide; altrimenti viene usata la durata Manim impostata **per slide**, fino
a un totale di dieci minuti. Una richiesta supporta fino a **30 slide**.
Una presentazione più lunga viene segnalata e non troncata silenziosamente.

Attivando anche **Voice**, il LLM prepara una spiegazione per ogni slide.
La voce viene generata prima del rendering e determina i tempi di ciascuna
scena. RAG, fonti web e documenti supplementari possono fornire contesto;
la presentazione allegata determina la sequenza. Con Assistant Off, inserisci
`Testo:` seguito da un paragrafo per slide, separato da una riga vuota.
Puoi anche allegare una traccia audio, senza Voice, da applicare al video.

Per slide senza testo estraibile serve **Vision** per una spiegazione o
ricostruzione basata sulle immagini. Viene passata una sola anteprima per
richiesta al modello, evitando di caricare l’intera presentazione in Vision.
Mantieni layout può conservare una slide immagine senza Vision, usando solo
le indicazioni dell’utente, senza inventare ciò che raffigura.

Il PPTX viene importato con un lettore portabile, senza richiedere PowerPoint.
Testi, immagini, posizioni e forme semplici sono supportati; SmartArt, grafici
complessi, segnaposto ereditati e particolari effetti possono essere approssimati
o non riprodotti. Gli avvisi compaiono nella chat. Per conservare l’aspetto di
una presentazione complessa, esportala da PowerPoint in **PDF** e allega il PDF.
Il vecchio formato `.ppt` deve essere convertito in PPTX oppure PDF.

Occorrono i componenti **Manim** e **Lettura documenti** dal Setup; per il PPTX
e le slide del canvas viene usato Microsoft Edge, già impiegato dall’export PDF.
Rendering e Python rimangono nello stesso AppContainer senza rete di Manim
libero. Il video finale e i sorgenti Python di ogni slide sono scaricabili dal
canvas; il manifesto di importazione conserva testo, coordinate e asset usati.
