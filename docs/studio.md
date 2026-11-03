# Studio e flashcard

Studio usa i progetti, gli allegati, il RAG e i collegamenti LLM già configurati
in H3-Chat. Ogni progetto mantiene le proprie fonti: non occorre un secondo
programma o un nuovo database vettoriale.

## Creare e studiare

1. Apri una chat del progetto e seleziona **Studio**.
2. Nelle impostazioni scegli Flashcard, Sintesi e briefing, FAQ, Guida allo
   studio, Cronologia oppure Dialogo a due voci. Imposta da 1 a 50 schede o
   sezioni e il livello. Puoi anche incollare un testo fonte.
3. Attiva RAG per usare le fonti del progetto, oppure allega un documento.
   Il prompt può specificare tipo, numero e livello; questi valori espliciti
   prevalgono sulle impostazioni.
4. Nel canvas usa **Mostra risposta**, **Ricordata**, **Da ripassare** e i filtri.
   **Spiega** crea una spiegazione usando le fonti della scheda. Le citazioni
   aprono il passaggio conservato, con pagina, URL o tempi quando disponibili.
5. **Modifica scheda** permette di correggere domanda e risposta. La modifica
   conserva le citazioni, che devi controllare, e fa ripartire il ripasso di
   quella versione. Tornando a una versione precedente ritrovi il suo ripasso.

Il lavoro viene salvato per piccoli gruppi di schede. Stop conserva i gruppi
già completati; **Completa schede mancanti** riprende senza rifare quelli pronti.
Il ripasso è separato per chat, lotto, scheda e contenuto.

## Viste e navigazione

Il canvas presenta una vista adatta al contenuto: flashcard con risposta nascosta,
sintesi e guide a sezioni, FAQ espandibili, cronologie su una linea del tempo e
dialoghi con le battute dei due conduttori distinte. **Leggi tutto** mostra il lotto
intero; **Studia / Ripassa** mostra una scheda alla volta. Le risposte possono
contenere elenchi, grassetti, tabelle Markdown e formule LaTeX. HTML e immagini
esterne nel testo non vengono eseguiti o caricati.

**Indice** consente di scegliere direttamente la scheda e cercare nel titolo o
nella risposta. La ricerca e il filtro di ripasso si combinano. **Mescola** cambia
l’ordine soltanto durante il ripasso; **Ordine originale** lo ripristina. La lettura
integrale mantiene sempre l’ordine del documento, anche per le cronologie.
Con il riquadro Studio selezionato, le frecce cambiano scheda e Spazio rivela la
risposta. Il canvas mantiene il contenuto e il lettore audio durante i sondaggi
di avanzamento che non cambiano il lotto.

**Prova a rispondere** permette di scrivere prima di vedere la soluzione.
**Confronta con la fonte** mostra risposta e citazioni, poi l’utente sceglie
Ricordata o Da ripassare. È un’autovalutazione, non una correzione automatica
dell’LLM. La bozza scritta resta disponibile spostandosi tra le schede nella
sessione del browser; non viene salvata nel documento né sincronizzata.

## Ripasso programmato

Il filtro **Da fare ora** include schede nuove, vecchi ripassi senza una scadenza
e schede la cui scadenza è arrivata. Una sequenza di risposte Ricordata propone
intervalli di 1, 3, 7, 14 e poi 30 giorni; Da ripassare azzera la sequenza e propone
un nuovo tentativo dopo 10 minuti. È una programmazione semplice di H3, non un
algoritmo FSRS/SM-2. Si può comunque ripassare una scheda prima della scadenza.
I vecchi progressi restano disponibili. Una modifica al contenuto ha un proprio
ripasso e una propria programmazione; riaprendo una revisione precedente si
ritrova la sua situazione.

## Tutor e fonti

**Fonti** mostra gli estratti conservati nel lotto e segnala quelli abbreviati.
Non è una misura percentuale di copertura dell’intero libro.
**Chiedi un chiarimento** consente una domanda sulla scheda e sulla spiegazione
precedente. Il tutor riceve soltanto le fonti citate da quella scheda; deve
dichiarare quando gli estratti non bastano. L’ultimo chiarimento citato viene
salvato nella scheda. Le risposte precedenti restano nelle revisioni del canvas,
non in una conversazione illimitata allegata alla scheda.

## Lotti ed esportazioni complete

In **Strumenti → Lotti del progetto** si aprono gli ultimi lotti salvati nelle
chat dello stesso progetto. Senza progetto, la lista riguarda la chat corrente.
La lista raggruppa le revisioni dello stesso lotto nella stessa chat e mostra
la più recente (massimo 50 lotti tra le ultime 500 revisioni); la cronologia del
canvas conserva anche le altre. Aprire un lotto non avvia generazioni.

**PDF completo**, **Word completo** e **HTML completo** in Strumenti esportano
tutte le schede, risposte, chiarimenti ed estratti fonte, anche se nel canvas è
visibile solo una domanda o è attivo un filtro. Anche i pulsanti PDF, Word e .md
in fondo al canvas usano l’intero Studio. PNG fotografa la vista corrente.
CSV e JSON rimangono disponibili nello stesso menu.

**Esporta CSV · Anki** produce fronte, retro e fonti. **Esporta lotto JSON**
conserva il documento con i suoi estratti. Il JSON può essere reimportato nello
Studio: riceve nuovi identificativi e inizia senza progressi di ripasso.
L'esportazione contiene gli estratti delle fonti: condividila soltanto con chi
può leggerli. Non è un pacchetto Anki APKG né una sincronizzazione con Anki.

## Fonti multimediali per tutto il progetto

Nel pannello Fonti trovi **Importa link, audio o video…**. La stessa importazione
è accessibile dalle impostazioni Studio. Sono supportati:

- pagine web pubbliche con testo estraibile;
- un URL YouTube con sottotitoli disponibili in italiano o inglese;
- audio e video caricati: Whisper legge la traccia audio, con il limite di
  durata già previsto da Trascrivi, e conserva i tempi.

Il testo viene indicizzato nel RAG del progetto ed è utilizzabile anche da chat,
slide e dagli altri strumenti con RAG attivo. Gli originali caricati restano
disponibili; le citazioni multimediali permettono di aprirli al tempo indicato.
Non viene analizzato visivamente il video. Se YouTube non offre sottotitoli
supportati, l'importazione lo segnala: puoi caricare il file e trascriverlo.
Un URL già presente richiede di scollegare la fonte precedente prima della
reimportazione, evitando di dichiarare aggiornato un testo rimasto vecchio.

L'Agente dispone di **create_study** e **import_public_study_source**. Per
importare da Internet deve avere Web e gestione progetti autorizzati; per
trascrivere audio/video serve anche il relativo permesso. Questi strumenti
rispettano Stop e la coda comune.

## Dialogo e audio facoltativo

Il tipo Dialogo crea prima uno script citato. Quando è completo, **Crea audio
a due voci** usa le due voci native configurate in Voice, che devono essere
distinte e disponibili. Riutilizza il testo salvato senza una nuova chiamata
LLM. Script, citazioni e audio restano nello stesso artefatto. Le limitazioni
CPU/GPU della voce continuano ad applicarsi; non viene installato un nuovo TTS.

## Limiti del grounding e verifiche

Studio non procede senza fonti. Il modello riceve istruzioni per rispondere
soltanto dagli estratti; ogni scheda o sezione deve includere citazioni con ID
validi. Il modello seleziona gli identificativi dei passaggi disponibili; il server
recupera le parole esatte dalla fonte, evitando citazioni ricopiate male. Una risposta non conforme ha una
sola correzione. Questo controllo verifica la provenienza, non dimostra che ogni
affermazione sia semanticamente corretta: usa i passaggi consultabili per
verificarla. Il recupero RAG e il budget del contesto possono selezionare solo
parte di un documento, non necessariamente il libro intero.

Il collaudo del 28 ottobre copre interfaccia, salvataggio, ripresa, permessi,
citazioni, importazioni ed esportazioni con LLM, rete, ASR e TTS simulati.
Indicizzazione lessicale e decodifica della traccia audio di un video sono state
eseguite realmente su CPU. Non è una misura della qualità di un modello LLM,
di Whisper, della sintesi vocale o dei sottotitoli YouTube dal vivo.

Il 29 ottobre una prova reale con Qwen locale ha completato un dialogo avanzato
di 10 battute con citazioni tratte esattamente dalle fonti. La prova non misura
la qualità delle due voci: la sintesi TTS rimane verificata con un motore simulato.

Il 3 novembre il collaudo della nuova interfaccia copre le sei viste, indice e
ricerca, tastiera, bozza della risposta, ordine casuale, programmazione del
ripasso, chiarimenti e libreria del progetto. Il browser verifica anche il
salvataggio e le esportazioni complete con fonti e modello simulati. Word e HTML
sono esportati realmente; un PDF reale su Edge CPU include tutte le schede e le
fonti, con testo ricercabile. Il controllo non misura una nuova generazione LLM
o la qualità di una nuova sintesi vocale.
