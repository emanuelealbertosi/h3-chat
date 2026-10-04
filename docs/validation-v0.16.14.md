# Verifica 0.16.14 · RAG visivo e scelta CPU/GPU nei progetti

## Implementazione

- Ovis usa il processore e il template nativi per testo e immagini, estrae l'ultimo
  token valido e normalizza i vettori da 2048 dimensioni. L'encoder visivo viene
  caricato soltanto con immagini RAG attive; audio e generazione restano esclusi.
- Le pagine illustrate PDF includono foto, grafici e diagrammi vettoriali.
  Sono renderizzate fino a circa 0,6 MP mantenendo il rapporto tra i lati e
  associate alla pagina originale. Le figure Word conservano il blocco di origine.
  Sono accettati anche PNG/JPEG/WebP nei progetti.
- La ricerca combina testo e immagini nello stesso spazio. Le figure recuperate
  sono copiate negli output della chat per conservare le anteprime delle citazioni.
  Vengono inviate al modello soltanto con Vision attivo e compatibile, entro il
  limite dei riferimenti; le figure non inviate sono indicate esplicitamente.
- I pulsanti CPU/GPU NVIDIA CUDA e l'opzione immagini sono nella finestra dei
  documenti del progetto. Le impostazioni valgono per tutti i progetti e si
  salvano immediatamente. La modifica viene rifiutata durante lavori attivi.
- RAG GPU e generazioni sono serializzati con attesa cancellabile. In modalità
  a richiesta vengono liberati i modelli precedenti prima di Ovis; in modalità
  residenti il caricamento rimane soggetto alla VRAM disponibile.

## Prove

- 324 test Python e 10 test JavaScript superati su Windows; interfaccia e
  bundle per installazioni da clone ricostruiti.

- Inferenza Ovis reale sulla GPU NVIDIA locale con i pesi originali selezionati
  dal filesystem. Due immagini sintetiche, cerchio rosso e quadrato blu, vengono
  recuperate correttamente dalle rispettive query testuali senza didascalie.
  Similarità: 0,587 contro 0,411 per il cerchio, 0,645 contro 0,292 per il quadrato.
  Caricamento 21,67 s; due immagini 2,88 s; due query 0,35 s. Questi tempi non
  costituiscono una misura della velocità su libri reali o su altra GPU.
- Prova completa locale con database separato: estrazione immagini, embedding,
  pubblicazione dell'indice e ricerca ibrida GPU. L'immagine pertinente viene
  recuperata senza corrispondenza lessicale; entrambi gli originali restano intatti.
- PDF sintetico con foto, diagramma vettoriale e pagina vuota: solo le prime due
  pagine ricevono un embedding visivo, conservando i numeri 1 e 2. Il PDF senza
  testo estraibile viene indicizzato correttamente in modalità visiva.
- Word con figura e didascalia, cache invariata, riparazione di un'anteprima
  mancante, isolamento tra progetti, migrazione dello schema e copia durevole.
- Un lavoro chat passa effettivamente l'immagine recuperata al messaggio Vision
  e conserva il riferimento e l'anteprima nei metadati della risposta.
- Verificati modello non Vision, Vision spento, limite di riferimenti, rifiuto di
  opzioni non valide, generazione in attesa dell'indicizzazione GPU e annullamento.
- Browser Edge desktop e 390 px: CPU/GPU, persistenza delle opzioni immagini,
  selezione multipla, caricamento a blocchi, trascinamento file/cartelle,
  deduplicazione, errore dentro la modale e assenza di overflow orizzontale.

La ricerca visiva non trascrive un intero libro mediante OCR e non crea
didascalie inventate. La qualità su foto e diagrammi reali dipende dal modello,
dalla domanda e dalla risoluzione della pagina. Per i dettagli minuscoli può
servire leggere direttamente la pagina originale a risoluzione maggiore.
I pesi, i documenti e i dati personali non sono inclusi nel pacchetto pubblico.

Riferimento: [interfaccia di retrieval ufficiale di Ovis](https://huggingface.co/ATH-MaaS/Ovis-Omni-Embedding-3B).
