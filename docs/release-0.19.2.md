# H3-Chat 0.19.2

## Studio

Viste dedicate per flashcard, sintesi, guide, FAQ, cronologie e dialoghi; indice,
ricerca, lettura integrale e navigazione da tastiera. Ripasso in ordine casuale,
prova a risposta libera con confronto alle fonti e autovalutazione. Programmazione
semplice del ripasso e filtro «Da fare ora», con conservazione dei vecchi progressi.
Domande di approfondimento sulle fonti della scheda e sulla spiegazione precedente.
Libreria dei lotti del progetto ed esportazione completa in PDF, Word, HTML e
Markdown, anche quando nel canvas è visibile una sola scheda. Tabelle e formule
nel materiale di studio. Il controllo delle citazioni verifica la provenienza,
non sostituisce la revisione didattica dei contenuti.

## Interfaccia e canvas

Modali ampie e uniformi, controlli leggibili, spaziature coerenti e adattamento
agli schermi piccoli. Impostazioni Studio riorganizzate. Ridotti i ridisegni del
canvas quando arrivano audio, musica o aggiornamenti di altre scene; mantenute
scrittura in tempo reale e anteprima. Scorrimento e zoom più stabili.

## Immagini e locandine

Editor visuale del layout MOSS con riquadri, sottoprompt e parole esatte, bozze
riutilizzabili e importazione/esportazione JSON. Il prompt mantiene la priorità.
Miglioramenti alla riproduzione di locandine allegate, ai controlli dei riferimenti
e alla gestione delle risposte strutturate dei modelli. PowerPoint modificabile
per le locandine: testi HTML, riquadri e immagini separati, con dimensioni coerenti
al formato pagina. Le scritte già incorporate nelle immagini restano raster e
gli effetti CSS più complessi possono differire da PowerPoint.

## Infografiche

Modalità Normale, Decorativa e Piano sequenza con camera e parallasse, regia più
rapida facoltativa e personaggi articolati sperimentali. Conservata la scelta del
modello immagini, degli sfondi video e dei pannelli. Corrette perdite di margini,
spaziature e dimensioni delle intestazioni nelle composizioni multipannello.
Controlli e composizione di immagini, musica e voci più coerenti.

## Video, voci e richieste

Numero e durata delle scene configurabili anche senza audio allegato, per T2V,
I2V e video con riferimenti. I segmenti nativi rispettano il limite del motore;
le scene più lunghe vengono composte mantenendo salvataggio e ripresa.
Ripristino più completo delle impostazioni delle richieste. Timbri italiani
Limpida e Aurora selezionabili in Voice, Studio e infografiche, con campioni
portabili; le impostazioni personali hanno precedenza. MOSS-TTS Local v1.5 resta
un motore facoltativo sperimentale, con pesi e runtime separati.

## Distribuzione

Pacchetti Windows x64, macOS Apple Silicon e Linux x64 verificati separatamente,
con controlli aggiuntivi su Kali. Installazione Windows via API senza GPU
conservata. I pacchetti non contengono chat, allegati personali, chiavi API o
pesi generativi. I motori e le funzioni CUDA restano esclusi dal percorso Mac;
la disponibilità effettiva dipende dai motori e modelli installati.
