# H3-Chat 1.0.0-rc.1

Prima candidata alla versione 1.0.0. La versione stabile rimane 0.19.2 durante
il collaudo. Nessun nuovo peso viene scaricato passando a questa versione.

## Novità rispetto alla 0.19.2

- Centro lavori con accesso ai risultati e revisione delle richieste.
- Undo/redo, copia/incolla e ordine dei livelli negli editor del canvas supportati.
- Preset con nome per le modalità di generazione e recupero dei parametri originali.
- Riutilizzo delle illustrazioni già create quando si ricarica una richiesta Slide;
  le immagini mancanti possono essere generate e aggiunte al catalogo del lavoro.
- Zoom immagini corretto, confronto affiancato e cursore per confrontare due immagini.
- Ricetta MOSS/Kromoss Turbo DMD2: 8 passi, CFG 1, Euler/Simple; recupero dei
  parametri precedenti quando Turbo viene disattivato.
- Qwen Image 2.1 standard e Turbo: fino a sei riferimenti e tele fino a 4 MP
  nominali, con allineamento alla griglia del motore. I 2 MP sono selezionabili
  nelle impostazioni della chat o dal prompt. I riferimenti sono codificati
  separatamente a circa 1 MP per evitare di ingrandirli insieme all'uscita.
- Guide di installazione, aggiornamento e limiti riallineate al candidato.

## Cosa collaudare

Seguire la [checklist della candidata](release-candidate-testing.md): nuova
installazione, aggiornamento dalla 0.19.2, conservazione dei dati, flussi completi
di creazione/modifica/esportazione e arresto/ripresa dei lavori supportati.
I rapporti allegati ai pacchetti distinguono i controlli automatici dalle prove
su motori reali. Una build riuscita non certifica ogni modello o GPU esistente.

## Limiti mantenuti

- macOS supporta Apple Silicon e il percorso CPU/Metal/API; i motori CUDA restano
  per Windows/Linux NVIDIA. I pesi generativi restano installazioni opzionali.
- Agent e controllo del PC, MOSS img2img, MOSS-TTS e personaggi articolati delle
  infografiche mantengono l'etichetta sperimentale e i controlli esistenti.
- L'export PowerPoint modificabile mantiene gli elementi supportati; testi già
  disegnati nelle immagini restano raster e alcuni effetti CSS possono differire.
- Le animazioni HTML restano nell'HTML; il PDF è statico e il PPTX non riceve
  animazioni native in questa candidata.
- RAG e citazioni indicano le fonti recuperate, senza garantire da soli la
  correttezza di ogni risposta. Le caratteristiche generative richiedono revisione.

## Dopo la 1.0

Brochure multipagina e animazioni PowerPoint native passano al
[piano successivo alla 1.0](post-1.0-roadmap.md). Il multiagente non è nel piano.

## Aggiornamento sicuro

Terminare i lavori e fermare H3 prima di aggiornare. Copiare la cartella `data`
con il servizio fermo e conservare `models`, percorsi esterni e impostazioni.
Seguire la [procedura di aggiornamento](release-candidate-testing.md#aggiornare-da-0192).
Non sovrascrivere un backup con i dati della candidata: serve per tornare alla
versione precedente, insieme al suo pacchetto originale.
