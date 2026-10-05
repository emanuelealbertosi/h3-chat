# Standalone, dispositivi e server esterni

## Scelta del dispositivo

In **Setup/Preferenze → Dispositivo per funzione** imposta LLM, immagini, Whisper
e ricerca semantica RAG. LLM/immagini possono seguire il profilo generale o scegliere
CPU/GPU. L'LLM conserva anche i layer GPU e i parametri del proprio preset. Immagini
native usano CPU, CUDA o Vulkan; Ming/Qwen usano CPU o CUDA. Nessun ripiego silenzioso
alla CPU se il backend scelto non è disponibile. Vision/mmproj della chat usa il dispositivo CPU/GPU scelto in chat (default CPU).
Musica ha il proprio selettore CPU/CUDA, Manim CPU/Cairo o GPU/OpenGL. MiniMax H3
video usa solo CUDA. PDF/Word, web e interprete numerico usano CPU.

Admin e chat avvisano che immagini e musica su CPU possono richiedere molto tempo.
Il composer indica la modalità dei motori scelti; ogni risposta conserva la modalità
effettiva del lavoro. Le stime di memoria escludono i pesi dei server esterni, perché
la memoria del server non è misurabile da questo PC.

## Client: collegare altri motori

LLM: **Setup → LLM tramite API**, protocollo Chat Completions compatibile.
Gli altri motori si collegano in **Server esterni · immagini, musica e video**.
Salva nome, indirizzo base, protocollo, ID modello, token e funzione. Premi
**Verifica server** per leggere i modelli, poi **Usa come default** o seleziona
il collegamento dalla chat. Sono disponibili più collegamenti.

Protocolli implementati:

| Protocollo | Funzioni | Indirizzo base | Parametri |
| --- | --- | --- | --- |
| H3 | Immagini crea/edit, musica, video | `http://192.168.1.10:8790` | Preset del modello sul server, con override del collegamento client |
| Images API compatibile | Immagini crea/edit | URL del provider, incluso `/v1` quando richiesto | Prompt, modello, dimensione, risposta `b64_json`; multipart per riferimenti |
| Forge / Automatic1111 | Immagini crea/edit | `http://127.0.0.1:7860` | Step, risoluzione, CFG, seed, negative prompt, sampler/scheduler, intensità edit |

Musica/video remoti richiedono un server H3: non è un connettore universale per ogni
API musicale o video. Le Images API devono accettare il formato base64 richiesto;
risposte contenenti solo URL non sono supportate. Più riferimenti usano `image[]`
se compatibile; Forge supporta un riferimento. Sui servizi pubblici/Forge il
dispositivo viene deciso dal server: il selettore CPU/GPU client è applicato dal
protocollo H3. Video H3 rifiuta CPU. Assistant prepara prompt tag in inglese o
istruzioni naturali secondo il collegamento; per musica/video prepara composizione
o piano con lo stesso LLM della chat. Assistant Off conserva il percorso diretto.

Il risultato remoto viene salvato localmente e mostrato come immagine, player audio
o player MP4, con download. Il canvas mantiene la stessa regola di destinazione.
Riferimenti allegati e istruzioni vengono inviati al server; LoRA locali del client
non vengono trasferiti al server. L'arresto H3 cancella anche il lavoro remoto;
con Forge/Images API termina l'attesa locale, ma il server può continuare il lavoro.

HTTPS è richiesto per Internet; HTTP è consentito su localhost o IP privati
10.x, 172.16–31.x, 192.168.x. Le chiavi sono protette con DPAPI dell'utente Windows,
non entrano nelle chat o nello stato pubblico. Cambiando indirizzo occorre reinserire
o rimuovere la chiave. I limiti degli output H3 sono 90 MB; gli adapter immagini
hanno limiti più piccoli e validano il tipo del file restituito.

## Server: usare H3-Chat su un altro PC

Sul PC che possiede i modelli, configura i motori standalone. In **Usa questo PC
come server H3** scegli accesso locale o rete locale e porta, poi **Avvia server**.
Copia il token mostrato una volta; il token non viene salvato tra i riavvii. In LAN
consenti la porta nel firewall di Windows. Il server si arresta dall'admin o chiudendo
il servizio dell'app. L'interfaccia amministrativa resta accessibile solo localmente.

Sul client, usa l'indirizzo del PC server e il token:

- LLM personalizzato: base `http://192.168.1.10:8790/v1`, ID di un LLM locale,
  formato JSON schema quando il modello lo supporta.
- Immagini/musica/video: protocollo **H3**, base `http://192.168.1.10:8790`, ID letto
  con **Verifica server**.

Il server espone soltanto elenco modelli e inferenza autenticata. Le richieste
condividono la coda seriale dell'app; un server occupato rifiuta nuove richieste.
Non espone navigazione filesystem, preferenze o chiavi. L'LLM server usa il proprio
dispositivo e preset; i generatori H3 ricevono la scelta CPU/GPU del client.
La scelta video resta GPU. Niente precaricamenti o copie dei pesi sul client.
