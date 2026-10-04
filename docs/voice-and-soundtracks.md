# Voice e video con traccia audio

## Voice: lettura e testi preparati dall’Assistant

In **Impostazioni → Setup/Preferenze → Voice** installa la base del motore
e i componenti Voice. Scegli dal filesystem le cartelle **Higgs Audio v3
Transformers** e **Higgs Audio v2 tokenizer**. I pesi sono letti dove si trovano.
H3-Chat contiene il proprio motore: non richiede H3-Audio né un suo servizio.
Il formato del modello deve includere tokenizer, Safetensors e adattatore Python.

Configura un campione femminile e uno maschile di 1–30 secondi. Il campione
determina timbro e accento; la sua trascrizione è facoltativa. Sono accettati
WAV, MP3, FLAC e OGG nei percorsi originali. Su altre installazioni questi
percorsi si scelgono nuovamente: campioni e pesi non sono distribuiti su GitHub.

Premi **Voice** in chat, apri **Voce e interpretazione** e scegli:

- **Leggi il testo**: pronuncia i caratteri inseriti senza riscriverli. Puoi
  separare istruzioni e parlato con `Testo: ...`.
- **Prepara lezione / riassunto**: Assistant On usa il LLM della chat, i
  documenti, le immagini visibili al modello, il RAG e le fonti web attive
  per scrivere il testo da pronunciare. Assistant Off legge il testo inserito.
- Voce femminile/maschile, registro naturale/grave/acuto, velocità e
  interpretazione. Sono indicazioni di recitazione supportate da Higgs,
  non trasformazioni garantite dell’identità vocale.

Anche «Leggi ad alta voce: ...», «Crea una lezione audio sul ...» e
«Genera un riassunto vocale del PDF» attivano la voce automaticamente,
se il riconoscimento è abilitato. Discussioni sulla voce restano testo.
La lingua del parlato dipende dal testo; l’Assistant segue la lingua richiesta.

GPU NVIDIA: circa 5,5 GB liberi a 4 bit, 7 GB a 8 bit, 12 GB BF16. CPU:
calcolo float32, circa 20 GB di RAM libera e tempi maggiori. La stima nel
Setup considera la memoria libera; il worker verifica le risorse prima
di caricare e libera il modello a fine lavoro o all’interruzione.

Il testo lungo viene suddiviso rispettando le frasi. Sono prodotti WAV,
testo completo e SRT con tempi per segmento. Il player e i download sono
nella chat oppure nel canvas scelto; il WAV è esportabile anche in MP3.
Una sintesi che raggiunge il limite del modello senza terminare viene
segnalata come errore e non pubblicata come audio completo.

## Audio nelle animazioni Manim

Allega una traccia e chiedi «Crea un’animazione Manim usando questo audio».
Il motore applica la traccia originale **dopo** il rendering: l’LLM non
deve ricordarsi di inserirla nel codice Python. L’animazione intera viene
adattata alla durata dell’audio, modificando la velocità senza aggiungere
un fermo immagine finale. Il codice originale resta scaricabile.

Con più audio indica `audio 1` oppure il nome del file da usare. `Senza
audio` e `audio solo come riferimento` disabilitano il montaggio. Una
richiesta che cita l’audio precedente può recuperare la traccia dalla chat.
Massimo 10 minuti per animazione con audio. I WAV/MP3 originali non sono modificati.
L’audio è ricodificato AAC nell’MP4: il contenuto viene conservato, non i byte.

## MiniMax H3: video lungo quanto l’audio

Senza traccia conservata, il default resta **15 secondi, 0,7 MP e 12 passi**.
Con una traccia audio allegata destinata al video, la durata viene ricavata
dal file: 42 secondi diventano **15 + 15 + 12**. `Audio solo come riferimento`
mantiene la normale durata del clip. Per il lip-sync chiedi esplicitamente
di sincronizzare le labbra con l’audio.

Assistant On prepara un piano continuo per le scene con lo stesso LLM
selezionato in chat. Assistant Off usa le istruzioni originali. Ogni scena
riceve il tratto temporale corretto della traccia e conserva i numeri dei
riferimenti. La memoria interna mantiene un fotogramma di apertura e le
ultime due conclusioni; l’ultimo fotogramma guida l’avvio della scena
successiva. Il formato scelto nella prima scena resta stabile.

Le scene sono montate e sincronizzate sulla traccia completa. Il finale
viene arrotondato al fotogramma e ritagliato alla durata dell’audio.
È possibile interrompere il lavoro durante qualunque fase. Massimo
10 minuti di audio. La memoria visiva aiuta la continuità, ma non garantisce
che il modello riproduca ogni dettaglio o un lip-sync perfetto.

Il video lungo con memoria è disponibile nel motore **standalone MiniMax H3**.
Per un server esterno questa funzione richiede un protocollo multiscena
compatibile; H3-Chat segnala il limite invece di inviare un clip troncato.
I clip ordinari tramite server esterno continuano a funzionare.

## Attesa e timeout Manim

Il messaggio di attesa distingue avvio del LLM, ragionamento, scrittura
del codice, rendering e montaggio. In **Preferenze → Parametri dei modelli
chat** puoi impostare il tempo massimo di risposta LLM per ciascun modello
(inizialmente 1800 secondi). Il tempo del rendering Manim è separato:
ogni tentativo riceve il budget configurato nelle opzioni Manim.
Un codice interrotto al limite di output viene indicato come tale: il
massimo effettivo, inclusi i token di thinking, dipende anche dal provider.
