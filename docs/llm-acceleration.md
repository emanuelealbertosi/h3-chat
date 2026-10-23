# Qwen27B ISTA IQ3_S e Orca IQ3_XXS ottimizzati in H3-Chat

Il runtime opzionale si installa nella cartella dell'app e usa
i pesi originali già collegati, senza copiarli. Il motore Standard,
le altre quantizzazioni e i backend CPU/Vulkan rimangono invariati.

## Attivazione

1. Termina i lavori H3-Chat e riapri l'app aggiornata. Se il servizio precedente
   è ancora aperto, usa Ferma-H3-Chat.bat e poi Avvia-H3-Chat.bat quando è inattivo.
2. In **Impostazioni → Preferenze → Parametri dei modelli chat**, seleziona
   `Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf` di ISTA oppure
   `Qwen3.8-27B-OrcaRouter-GSQ-RCO-IQ3_XXS-v2.0-qatfa.gguf` di Orca.
3. Seleziona backend CUDA e dispositivo LLM GPU/eredita, quindi premi
   **Applica 128K + MTP2 · Vision CPU** per ISTA oppure
   **Applica 128K + MTP4 · Vision CPU** per Orca, quindi salva le impostazioni.
4. Conserva **Memoria → A richiesta** per liberare la memoria fra i modelli
   della catena. Non avviare contemporaneamente il server standalone Qwen27B.

Il riconoscimento usa il GGUF reale, indipendentemente dal nome assegnato
al collegamento nel catalogo. Non serve collegarlo una seconda volta se è già
presente. Il modello chat predefinito non viene sostituito
quando configuri il preset di Orca; selezionalo nella chat quando vuoi usarlo.

I valori salvati precedenti (sul PC: contesto 50.000 e MTP1) non vengono
modificati dall'installazione. L'attivazione è esplicita e il preset è per
modello. Il pulsante imposta 131.072 token, tutti i layer GPU, MTP2 per ISTA
oppure MTP4 per Orca, e thinking
low; conserva temperatura, timeout e limite di risposta, salvo limitarlo a
65.536 se eccede metà del nuovo contesto. Imposta anche Vision CPU, che è una
preferenza condivisa. Per tornare indietro scegli **Motore → Standard**;
contesto e MTP non vengono abbassati automaticamente.
Standard non applica la cache Q4/finestra MTP di questo profilo: per ripristinare
la configurazione precedente imposta anche 50.000 di contesto e MTP1, con
limite di risposta non superiore a 25.000. Non presumere che Standard abbia
lo stesso consumo di memoria a 128K.

## Rilascio di memoria: stessa catena, stesso proprietario

Il server viene creato dalla normale `Session` di H3-Chat, con porta privata
su 127.0.0.1 e chiave effimera. Non è un servizio esterno, non si avvia da solo
e non cambia l'accesso remoto dell'app.

Con **A richiesta**, `_activate` chiude e attende il processo LLM prima di
creare la sessione del modello successivo: immagini, musica o video. La
gestione RAG e il blocco condiviso della GPU restano invariati. KV cache,
stato MTP e contesto CUDA appartengono al processo chiuso. La cache facoltativa
dei file resta limitata, recuperabile dal sistema e senza blocco della RAM.
Il comportamento esistente del motore immagini tenuto pronto rimane separato
e non mantiene il processo LLM. **Libera memoria**, stop e interruzione usano
gli stessi metodi di chiusura di prima. La modalità **Residenti** mantiene
invece i modelli, come già previsto: non viene convertita automaticamente.

## Profilo e requisiti

- Solo i GGUF esatti verificati: ISTA IQ3_S, 12.120.016.960 byte, oppure Orca
  IQ3_XXS v2.0 qatfa, 10.442.846.464 byte. Entrambi qwen35, 65 blocchi e MTP
  incorporato. Altre quantizzazioni/versioni non vengono abilitate automaticamente.
- Windows e una sola NVIDIA RTX 50 (build CUDA sm_120); almeno **15.550 MiB
  VRAM liberi a 128K per ISTA**, **15.000 MiB per Orca** e **16 GiB RAM
  disponibili** al caricamento. A 64K, scelti esplicitamente, le soglie sono
  14.398 MiB ISTA / 13.848 MiB Orca: viene sottratta solo
  la cache Q4 principale risparmiata (1152 MiB), mantenendo il margine di
  sicurezza del test 128K e la stessa bozza MTP. Non viene ridotta automaticamente
  la dimensione del contesto.
- La soglia VRAM è prudenziale, non una misura di OOM. Oscillazioni del desktop
  entro 128 MiB sotto tale soglia consentono un tentativo con avviso di margine
  stretto, usando una piccola parte della riserva già inclusa nella stima.
  Contesto, cache e layer GPU restano invariati. Oltre questa tolleranza il
  caricamento resta bloccato e il messaggio mostra memoria libera e differenza.
- MTP attivo con 2 token ISTA / 4 token Orca, tutti i layer GPU, Vision CPU oppure spenta.
  Nessun offload parziale o riduzione automatica del contesto se manca memoria.
- Contesto principale 16K–128K, cache K/V Q4_0; **solo la cache della bozza MTP
  ha finestra 8192**. Non è un limite 8K per la conversazione principale.
- Batch 2048, microbatch ISTA 256 testo / 128 Vision CPU, Orca 512 in entrambi
  i modi; Flash Attention e
  campionamento backend, con checkpoint e cache prompt RAM 1024 MiB.

Le librerie private sono sotto
`runtime/accelerators/qwen27-mtp-555d1ec-window8k`, fuori dal percorso di ricerca
del motore Standard. SHA-256 verificati prima dell'uso; una modifica alle
librerie cambia la sessione e richiede un nuovo caricamento. Le variabili
della bozza sono impostate solo nell'ambiente del processo LLM, non globalmente
e non nei processi immagini/musica/video. Il profilo rifiuta opzioni incompatibili
prima di sostituire un altro modello della catena.

## Verifiche e limiti

I test senza inferenza verificano chiusura LLM **prima** dell'avvio del modello
successivo per immagini/musica/video, ritorno alla chat, riuso, cambio runtime,
stop, interruzione, ambiente isolato, integrità delle librerie, opzioni Vision,
preset espliciti e controlli di memoria. I test esistenti proteggono la gestione
Residenti e del motore immagini mantenuto pronto.

Verifica finale del 6 ottobre 2026: suite Python completa **370 test superati**;
suite dedicata **23 test superati**, inclusi nella suite completa; interfaccia
ricostruita e **13 test JavaScript superati**. Verificati anche gli SHA-256 del
runtime installato. I dati reali dell'app sono stati consultati solo in lettura;
non è stato riavviato il servizio in uso. I test HTTP usano server di prova
localhost e cartelle temporanee separate dai dati reali.

Il motore integrato ISTA è stato misurato realmente a **65.536 token, MTP2 e
Vision CPU**, usando Engine.start_llama/completion con dati temporanei:

| Richiesta | Prefill token/s | Generazione token/s |
|---|---:|---:|
| Breve, thinking low | — | 76,69 |
| Nuovo prompt ~8K | 1296,78 | 77,80 |
| Continuazione ~8K in cache | — | 84,51 |
| Nuovo prompt ~62K | 965,09 | 60,35 |
| Continuazione ~62K in cache | — | 64,90 |

Report finale: `work/accelerator-benchmarks/h3-20261006-65536-vision-native-mtp2-samplingfix.json`.
Tutti i nove controlli superati: recupero dei codici, calcolo 400/3400 con low,
Vision (3,44 secondi), contesto/MTP reali, riuso e passaggio della catena.
Il processo LLM è stato chiuso **prima** dell'attivazione del modello immagini
di prova: VRAM usata/libera prima e dopo **756/15.240 MiB**, nessun LLM residuo
nel pool. Minimo libero durante il test: 1637 MiB VRAM e 16,23 GiB RAM.
La sessione successiva è una fixture: non sono stati caricati pesi immagini;
la chiusura del processo LLM e il rilascio della sua memoria sono invece reali.

Il budget reasoning=0 ridondante viene omesso solo nel profilo ottimizzato
quando il thinking è spento: evitava inutilmente il campionamento backend.
I budget non nulli low/medium/high restano applicati; Standard non cambia.

**128K integrati ISTA non sono stati misurati con l'attuale memoria libera**:
15.240 MiB non soddisfano la soglia 15.550. Il test 64K è esplicito e non
modifica il preset reale 50.000/MTP1/Standard/A richiesta. Non chiudiamo altre
app né riduciamo automaticamente il contesto. A 128K il motore standalone di
origine ha già misurato circa 42–43 token/s e 702–749 di prefill vicino a 126K:
sono risultati standalone, non misure dell'integrazione H3-Chat.
Il risultato ISTA non va confuso con i test separati di Orca: il preset
e il controllo di memoria sono ora distinti per modello nello stesso runtime.

Un contesto 128K quindi **non garantisce 60 token/s o 1500 di prefill**.
Dipendono da lunghezza, percentuale di accettazione MTP e memoria libera.
Le stime di memoria dell'app usano i 16 blocchi di attenzione completa e cache
Q4 del profilo ibrido, ma non sostituiscono una misurazione del picco.

## Orca: prova reale del motore integrato a 128K/MTP4

Misurato usando il vero Engine H3, con porta privata autenticata, VisionCPU,
dati temporanei e lo stesso file Orca già collegato al catalogo:

| Richiesta | Prefill token/s | Generazione token/s |
|---|---:|---:|
| Breve, low, budget risposta2048 | — | 72,44 |
| Nuovo prompt ~8K | 1181,34 | 77,43 |
| Continuazione ~8K | — | 81,07 |
| Nuovo prompt126.047 token | 698,51 | 52,78 |
| Continuazione ~126K | — | 54,98 |

Primo testo del prompt126K dopo181,13s; continuazione dopo0,66s. Recupero
dei codici casuali a inizio/metà/fine superato su entrambi i prompt e sui
followup. Contesto effettivo131072, MTP4 e speculazione confermati, stessa
sessione riusata. Minimo campionato libero1030MiB VRAM e11,19GiB RAM.
Durante questa prova è girata anche la suite di test senza inferenza: il
consumo RAM include quella attività. Dopo il rilascio erano disponibili
25,31GiB RAM. Nessun arresto di sicurezza, nessuna promessa di assenza di
spill con carichi esterni o prompt diversi (la memoria condivisa non è
misurata direttamente).

Report: `work/accelerator-benchmarks/h3-20261006-orca-128k-vision-native-mtp4-utf8.json`.
**Il report completo conserva un controllo aritmetico fallito**: con
max_tokens512/low (budget thinking64), il modello ha risposto391 invece di400.
Non è nascosto né riscritto come PASS. Contesto, recupero codici, Vision e
tutti i controlli del ciclo di vita sono passati. L'errore non prova da solo
la causa; il budget corto è un limite da considerare, non una garanzia che
un budget maggiore risolva qualsiasi errore del modello.

Prova successiva con max_tokens2048/low (budget thinking256):400/3400 corretti,
Vision corretta in4,06s e **tutti i10 controlli superati**. Report:
`work/accelerator-benchmarks/h3-20261006-orca-128k-vision-native-mtp4-budget2048.json`.
Questo è un test breve a128K allocati, non un secondo benchmark a126K occupati.
Non vengono aumentati automaticamente i budget del modello: il pulsante
conserva il limite di risposta salvato; per riprodurre la prova positiva scegli
2048. Il primo avvio di prova senzaUTF8 si è interrotto prima del caricamento
per la codifica terminale cp932; anche quel report resta conservato.

In entrambe le prove il processo Orca è morto **prima** dell'attivazione
del modello immagini fixture, senza LLM residuo nel pool. Nell'ultima,
VRAM prima/dopo identica:879MiB usati,15117MiB liberi; RAM dopo25,85GiB.
La fixture non carica pesi immagini reali: il rilascio del processo LLM
e della sua memoria è reale. I test senza GPU coprono anche musica/video
e il ritorno alla chat con ricaricamento Orca. Server di prova lasciati spenti;
servizio H3 in uso e preset reali non riavviati/modificati.

Per ripetere la prova completa solo a GPU libera:

```powershell
.\runtime\python\python.exe -X utf8 scripts\benchmark_llm_accelerator.py --label orca-verifica-nuova --model orca-iq3xxs --model-path ".\models\Qwen3.8-27B-OrcaRouter-GSQ-RCO-IQ3_XXS-v2.0-qatfa.gguf" --mmproj ".\models\mmproj-Qwen3.8-27B-BF16.gguf" --context 131072 --long 8000 126000 --arithmetic-tokens 2048 --vision
```

Sostituisci i percorsi d'esempio con i tuoi file: `--model-path` è obbligatorio;
`--mmproj` è facoltativo se il proiettore col nome originale è accanto al GGUF.
Il corpus iniziale proviene dai sorgenti `h3chat/` di questo checkout; con
`--corpus percorso.txt` puoi fornire lo stesso testo per confronti ripetibili.
La figura di test Vision (quadrato rosso e cerchio blu) viene creata su CPU;
`--vision-image percorso.png` permette di sostituirla con una figura equivalente.
Non vengono cercati modelli, documenti o immagini nelle cartelle di altri utenti.
Usa lo stesso corpus e la stessa immagine per confrontare le prestazioni:
i valori storici sopra non misurano queste nuove fixture predefinite.

Lo script non sovrascrive report con lo stesso nome, rifiuta server standalone
già attivi e ferma soltanto il processo posseduto dal suo Engine temporaneo.

## Installazione locale e provenienza

Il runtime di riferimento proviene da un motore già verificato: llama.cpp commit
`555d1ec9daa4564cb06adb39c469acfdcd1d1e93`, con modifica alla sola llama-common
per limitare la cache della bozza. Questa compilazione personalizzata deve
essere fornita esplicitamente: lo script non può ricostruirla dai soli hash.
Le dipendenze CUDA 12.8 e Microsoft CRT sono incluse nella cartella privata;
il Toolkit serve all'installatore locale, non al successivo avvio del runtime.
Le licenze originali e il manifest con hash/provenienza sono nella stessa cartella.
Spazio aggiunto dalla prima installazione: circa **870 MB**, nessuna duplicazione
dei pesi. L'aggiunta Orca riusa quelle stesse librerie, senza altre copie o
download. L'identificatore legacy del manifest contiene ancora iq3s-mtp2:
identifica gli stessi file attestati, non il profilo del modello; i controlli
per ISTA/Orca, MTP e memoria sono separati nel codice dell'app.

Per installare quella build verificata, ad app ferma:

```powershell
.\runtime\python\python.exe .\scripts\install_qwen27_accelerator.py --source ".\motore-verificato" --cuda "$env:CUDA_PATH" --license ".\llama.cpp\LICENSE"
```

`--source`, `--cuda` e `--license` sono obbligatori: sostituisci gli esempi
con la directory del motore attestato, il Toolkit CUDA 12.8 e la licenza
llama.cpp originale. Se `CUDA_PATH` non è configurato, passa il percorso
completo del Toolkit. Le librerie Microsoft vengono cercate in
`%WINDIR%\System32`, modificabile con `--system32`.
Lo script controlla gli hash prima della copia e non
sovrascrive librerie installate differenti. Non scarica nulla e non usa GPU.
Il runtime opzionale non è incluso automaticamente nel pacchetto portabile
generico: la build sm_120 non è un backend universale per altri PC.
