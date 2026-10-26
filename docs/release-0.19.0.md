# H3-Chat 0.19.0

## Agente e strumenti

- Modalità Agente distinta dagli strumenti normali, con pulsante rosa quando
  inattivo e rosso quando selezionato. Assistant rimane disponibile.
- Preferenze Agente dedicate: budget token prudenziale, passaggi, chiamate,
  tempo attivo, dimensione download, numero immagini e ruoli di preparazione.
- Autoapprova richiede un avviso esplicito. Non concede accesso al PC e non
  approva privilegi amministratore o l'inserimento di chiavi API.
- H3, cartella Sandbox e Globale conservano perimetri distinti. File, codice,
  esecuzione, ricerca web, download e installazione di LoRA compatibili usano
  strumenti con risultati e permessi verificati. I tool nativi H3 hanno precedenza.
- Da due a quattro ruoli preparano il compito in sequenza con lo stesso LLM e
  budget condiviso; un solo coordinatore esegue gli strumenti.
- Video, immagini, slide, infografiche, musica, voce, trascrizione, documenti,
  calcolo e Manim sono collegati ai servizi H3. I modelli generativi restano
  soggetti ai permessi e alla coda del servizio.
- Le richieste MOSS Turbo e i parametri espliciti di seed, formato e megapixel
  vengono conservati anche se il coordinatore riscrive il prompt visivo.
- Corrette la lettura dello stato Agente e la pubblicazione dei file scaricati.

## Video e slide

- FastH3 Omni usa un profilo dedicato con otto passi e VSA. Corretto il
  riconoscimento dei banchi di uscita distillati e dei canali fisici video/audio.
- Corrette le modifiche alla slide indicata e i casi in cui istruzioni interne
  del motore venivano riportate tra i contenuti della presentazione.
- I formati globali e quelli delle singole immagini vengono preservati nei lotti.

## Piattaforme

- Windows mantiene l'installazione senza compilatori e la modalità CPU/API.
- macOS Apple Silicon include motori CPU/Metal e strumenti documenti/Manim;
  le funzioni e i motori CUDA non fanno parte del pacchetto Mac.
- Linux x64 include la base CPU/API e componenti NVIDIA opzionali. I pacchetti
  sono verificati su Ubuntu e Kali; l'eccezione AppArmor per bubblewrap è una
  scelta esplicita dell'installer, con conferma amministratore.
- Ogni archivio viene accompagnato da checksum e rapporto di verifica. Dati
  personali, credenziali e pesi generativi non sono inclusi.

## Limiti dichiarati

L'Agente non controlla ancora visivamente il desktop con mouse e tastiera. I
ruoli multipli non sono processi concorrenti con modelli diversi. La modalità
Globale usa i privilegi del processo: l'elevazione richiede sempre una conferma
nativa dedicata.

Lo steering additivo locale è opzionale e sperimentale. Nessun vettore è incluso
o attivato automaticamente: non è stato verificato un vettore pubblico per il
checkpoint ISTA dell'utente. I candidati projectivi/GLP non vengono caricati
come vettori additivi. Questa funzione non promette una variante abliterated.
