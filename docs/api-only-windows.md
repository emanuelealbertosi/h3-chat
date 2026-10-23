# Windows senza GPU · API e RAG locale

H3-Chat funziona su Windows 10/11 x64 anche senza scheda video dedicata. Chat,
Assistant, canvas, slide e infografiche possono usare un modello remoto: nessun
LLM o contesto generativo viene caricato nella RAM o VRAM del PC. Per le
illustrazioni, la musica e i video si possono configurare server esterni separati.

## Installazione leggera da GitHub

1. Scarica il repository oppure esegui `git clone` ed estrai tutto in una cartella
   scrivibile, fuori dallo ZIP. Apri **Installa-API-senza-GPU.bat**.
2. L'installatore prepara Python privato, interfaccia e strumenti PDF/Word/FFmpeg.
   Non richiede Python di sistema, Node.js, compilatori, CUDA o privilegi di
   amministratore. Non scarica motori generativi locali, modelli o pesi GPU.
3. Al termine apri **H3-Chat.exe** o **start.bat**. Nel Setup, **Provider LLM**,
   configura indirizzo, chiave API e ID del modello. Premi **Usa in chat**.
   Router e Assistant useranno lo stesso collegamento.
4. Per immagini e altri media aggiungi i server in **Server esterni**. Immagini:
   protocollo H3, Forge/A1111 oppure Images API con immagini base64. Musica e
   video: protocollo H3. Non tutti gli endpoint proprietari sono intercambiabili.
5. Salva le impostazioni. Non occorre installare il runtime CUDA, scegliere un
   modello locale o premere **Installa motori** per usare le API.

Il profilo API iniziale sceglie CPU per i componenti locali e non preseleziona
modelli generativi. Trascrizione automatica e voce locale sono disattivate;
restano opzioni installabili separatamente. Le funzionalità GPU/locali restano
disponibili se in futuro aggiungi hardware e modelli compatibili.

Sulla versione ZIP portabile completa gli strumenti CPU possono essere già
inclusi: non occupano memoria GPU e non caricano pesi automaticamente. Anche
senza reinstallare, **Setup → Configura per API · nessuna GPU** prepara gli stessi
dispositivi e mantiene gli eventuali provider configurati. È una bozza da
salvare; deseleziona i modelli generativi locali senza cancellarli.

## RAG locale leggero

La ricerca per parole funziona subito, senza pesi o inferenza. Per la ricerca
semantica vai in **Preferenze → Progetti e ricerca nei documenti**, scegli un
embedding e **CPU**, installa i suoi componenti e scarica i relativi pesi. Per
EmbeddingGemma 2 il runtime CPU è separato dai motori generativi; il vecchio
EmbeddingGemma GGUF usa invece il motore llama CPU, installabile dal Setup.

I documenti e l'indice rimangono sul PC. Con un LLM esterno gli estratti recuperati
vengono inviati al provider insieme alla domanda; le immagini selezionate
richiedono un provider con Vision attivo. La velocità di indicizzazione dipende
dalla CPU, dalla RAM e dal numero di pagine.

## Aggiornamenti e verifica

Termina i lavori, esegui **stop.bat**, aggiorna il repository e riapri
**Installa-API-senza-GPU.bat**. L'installatore verifica le revisioni e i checksum,
riutilizza componenti validi e conserva chat, credenziali, modelli e preferenze
esistenti. Il profilo iniziale viene applicato solo alla creazione di un nuovo
database; una reinstallazione non converte un profilo GPU già configurato.

La verifica automatica simula una cartella di installazione vuota, senza pesi,
motori nativi o GPU: chat, router, canvas e immagini vengono eseguiti contro
provider locali simulati, con avvio di motori locali e download automatici
vietati dal test. Non equivale a una prova su ogni hardware o su ogni provider
commerciale. I servizi remoti richiedono connessione e le rispettive credenziali.
