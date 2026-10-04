# Verifica 0.16.11 — Voice + Manim

Il flusso combina copione, TTS standalone e Python Manim completo in una sola
richiesta. Il RAG e il contesto degli allegati/web vengono preparati prima del
copione e mantenuti anche nelle richieste di codice delle singole scene.

## Verifiche automatiche

- 308 test Python passati; sette controlli JavaScript passati.
- Routing esplicito Voice + Manim e riconoscimento dal prompt, senza attivare
  altri strumenti quando la richiesta è una domanda sul loro funzionamento.
- Tempi reali delle scene, pause, intervalli non validi e narrazione incompleta.
- RAG trasmesso al copione e al codice; vincolo del progetto “solo fonti”.
- Assistant Off e `Testo:` conservano il parlato senza riscriverlo.
- Numero di scene esplicito controllato prima della sintesi vocale.
- Errori JSON ritentati una sola volta; rete, credito, limite di token e
  cancellazione non provocano tentativi automatici aggiuntivi.
- Ripresa dopo interruzione, con voce e clip completati riutilizzati e verificati
  tramite SHA-256. Rigenera su un risultato completato crea un lavoro nuovo.
- Montaggio PyAV reale: due clip entrambi lunghi due secondi vengono adattati
  a scene vocali di uno e tre secondi. La transizione avviene a un secondo,
  verificando i colori di tutti gli 80 fotogrammi, invece che a metà video.
- Bundle precompilato allineato ai sorgenti per l'installazione senza compilatore.

## Prova completa su Windows

Fonte RAG sintetica: circuito con batteria da 12 V, resistenza da 6 Ω,
legge di Ohm e corrente da 2 A. Provider LLM configurato tramite API;
Higgs Audio v3 e codec v2 reali su GPU; Manim Cairo e LaTeX reali eseguiti
nell'AppContainer già utilizzato dall'app. Dati e chat di test separati
dalla produzione, senza modificare H3-Audio o H3-Studio.

Una prima prova completa ha prodotto 233 fotogrammi, voce da 15,52 s e
video da 15,5333 s. Una seconda prova con due scene ha conservato il WAV
da 15,46 s dopo una risposta JSON non valida del provider. Rigenera ha
riutilizzato quella voce senza una seconda sintesi e prodotto entrambe
le scene, il montaggio finale da 232 fotogrammi e il video da 15,4667 s.
Il SHA-256 del WAV è rimasto identico. Le fonti RAG sono state verificate
in ogni richiesta di codice. Il risultato è disponibile solo nel canvas
selezionato, insieme a WAV, testo, SRT, copione con tempi e sorgenti Python.

Il montaggio verifica la sincronizzazione ai confini delle scene. Le frasi
ricevono tempi TTS misurati e vengono passate al codice generato, ma la qualità
dell'animazione e la corrispondenza dei singoli gesti alle parole dipendono
dal LLM. La durata richiesta guida la lunghezza del copione; la durata finale
segue l'audio completo. La differenza video/audio resta entro un fotogramma.
