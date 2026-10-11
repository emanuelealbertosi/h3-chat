# Modificare un video

**Modifica video**, vicino alla Galleria, apre un video dalla galleria oppure un
MP4 caricato dal PC. Puoi anche usare **Modifica clip** sotto un video già generato.

Per i video MiniMax generati nell'app si recuperano i clip, i prompt, i riferimenti
e l'audio conservati. Un MP4 esterno non contiene queste istruzioni: viene mostrato
in intervalli temporali di massimo 15 secondi, senza riconoscimento automatico
degli stacchi. L'ultimo intervallo può essere più corto. Sono ammessi MP4 fino a
64 MB e 10 minuti; quelli già generati si scelgono dalla galleria senza ricaricarli.

1. Seleziona uno o più clip.
2. Scegli **Intera clip** oppure **Solo un tratto** e indica i tempi relativi al clip.
3. Scrivi cosa cambiare e scegli **Riferimenti** oppure **I2V · immagine iniziale**.
4. Per un video esterno viene proposta la sua immagine iniziale; scegliendo solo
   un tratto, il fotogramma originale viene recuperato dall'inizio del tratto.
   Puoi sostituirlo con una tua immagine.
5. Avvia **Crea nuova versione**. Solo i tratti scelti vengono generati da MiniMax;
   il montaggio conserva il resto del contenuto e la traccia audio originale.

I2V ricrea il tratto da un'immagine, non modifica pixel per pixel il video originale.
Il movimento e il raccordo possono cambiare. I video esterni vengono normalizzati
a 24 fps per il montaggio, con ricodifica H.264; la dimensione finale rimane quella
del filmato importato, senza deformare la parte generata. L'originale resta conservato.
La nuova versione può essere ritoccata ancora con **Modifica clip**; **Ricrea video**
richiede invece le istruzioni originali di una generazione MiniMax completa.

## Remix dell'audio

**Remix**, vicino alla Galleria, oppure **Remix audio** sotto un video, modifica
tutta la traccia o un intervallo: **A = 0** indica la fine del filmato.

- **Audio caricato**: sostituisce la traccia con un file scelto dal PC o dalla galleria.
- **Voce · Higgs**: pronuncia il testo esatto con le preferenze Voice. Puoi scegliere
  interpretazione e campione da clonare; la modalità Radio mantiene il ritmo 8–12%.
- **Musica · YuE2**: genera una nuova traccia con testo e stile indicati.
- **Nuovo canto sulla base**: separa voce e accompagnamento, ricava la melodia con
  SheetSage2/MERT, genera il nuovo canto YuE2 e lo riallinea alla base originale.
  Puoi fornire un ABC manuale; in quel caso si adatta la durata senza verifica nota per nota.
- **Cambia timbro · clona**: conserva le parole e la melodia e converte il timbro
  vocale con SeedVC usando il campione scelto.
- **Solo base**: rimuove la voce riconosciuta da HTDemucs dal tratto scelto.

**Conserva la base originale** è disponibile anche con audio caricato o Higgs.
Il montaggio audio copia il flusso video senza ricodificarlo. La nuova traccia WAV
mantiene i campioni originali fuori dall'intervallo; l'MP4 contiene audio AAC.
Il movimento delle labbra resta invariato: per rifarlo usa poi Modifica clip e Lip-sync.

Nei **Parametri avanzati** puoi scegliere inizio e volume della nuova traccia,
adattamento della durata e ABC. Una traccia troppo lunga viene rifiutata se non
scegli esplicitamente **Adatta durata** o **Loop**: il programma non taglia le parole
per farle entrare. Con una voce più breve lo spazio residuo viene completato con silenzio.

## Installazione autonoma

Nelle preferenze avanzate, **Remix audio e video**, installa il montaggio audio e
il motore CPU o GPU. Per ricavare la melodia installa anche **Lettura spartiti**:
usa Python 3.11/Torch/Transformers isolati dentro H3-Chat. Il download iniziale
è consistente; non avviene durante una normale richiesta Remix.

Seleziona dal filesystem HTDemucs e SeedVC GGUF e, per la melodia, le cartelle
Transformers SheetSage2 e MERT v2. I pesi rimangono nelle cartelle scelte; non sono
copiati né inclusi su GitHub. Le richieste utilizzano il modello YuE2 scelto nelle
preferenze Musica e le impostazioni Higgs delle preferenze Voice.

CPU/GPU, thread e conversione SeedVC 30/50/100 passi sono configurabili. Su CPU
separazione, conversione e canto possono richiedere molto tempo. Tutte le operazioni
usano la coda condivisa dell'app: un solo lavoro per utente e un solo lavoro GPU
alla volta. Stop termina anche i processi figli. Ogni account usa i propri file.

Il motore è interno a H3-Chat: non chiama H3-Music o un altro server. I runtime
precompilati sono scaricati dalla release H3-Chat e verificati con SHA-256.
