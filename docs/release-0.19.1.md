# H3-Chat 0.19.1

## Locandine

Composizione completa con sfondo MOSS e tipografia HTML/SVG espressiva, font locali,
effetti e controlli di ingombro. I testi preparati possono essere distribuiti in
aree diverse senza falsi errori di ordine; i controlli continuano a respingere
contenuti omessi, ripetuti, sovrapposizioni e ritagli. Le revisioni tipografiche
riutilizzano lo sfondo salvato. Esportazione PowerPoint a pagina intera per
conservare la resa: i testi restano modificabili in H3, non come caselle nel PPT.

## Studio e fonti

Flashcard, sintesi, FAQ, guide, timeline e dialoghi dalle fonti del progetto.
Citazioni consultabili, spiegazioni, ripasso, ripresa degli elementi mancanti,
esportazione CSV/JSON e reimportazione. Il modello seleziona passaggi identificati;
il server recupera la citazione originale. Il dialogo può usare due voci native
configurate, conservando l'identità di chi parla anche fra turni consecutivi.

Importazione nel RAG di pagine pubbliche, sottotitoli YouTube disponibili e
trascrizioni audio/video tramite i componenti esistenti. Il video non viene
analizzato visivamente. Il controllo delle citazioni verifica la provenienza,
non garantisce da solo la correttezza semantica di ogni affermazione.

## Altre modifiche accumulate

Browser interattivo dell'Agente, consenso Web e download video pubblici; flusso
della chat progressivo; modalità di interfaccia base/avanzata; filtro iniziale
della galleria per progetto; gestione delle richieste immagine-video e dei
parametri di layout MOSS. Le funzioni rispettano permessi e coda condivisa.

## Compatibilità e limiti

Windows, macOS Apple Silicon e Linux x64 mantengono i rispettivi percorsi di
installazione. Su Mac restano esclusi i motori CUDA. Pesi, credenziali, documenti
e dati personali non fanno parte dei pacchetti. Le prove CI dei pacchetti non
sono benchmark di generazione su una GPU fisica.

## Esportazioni e selezione delle fonti

Eliminato il limite di 64 MiB del documento HTML usato dalle esportazioni PDF/HTML.
Le relative richieste non sono più fermate dal tetto generale di 90 MiB.
Restano i tempi e le risorse effettivamente disponibili del browser di stampa.
La modifica non aumenta i limiti di caricamento degli allegati o degli altri endpoint.
