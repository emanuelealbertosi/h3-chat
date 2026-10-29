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
