# Steering LLM — verifica del 26 ottobre 2026

Stato per la 0.19.0: opzione additiva implementata e verificata con fixture
strutturali e avvio simulato; nessun vettore reale installato o applicato,
nessuna prova GPU di steering. L'installazione automatica di un vettore per
l'ISTA resta non disponibile, non viene dichiarata completata.

## Opzione implementata

Nelle opzioni tecniche LLM e nelle Preferenze dello stesso modello è disponibile
«Steering · sperimentale», disattivato per default. Conserva per modello percorso
GGUF, intensità (0 è neutro) e layer. La prima famiglia ammessa è qwen35 27B,
5120 dimensioni, 64 layer principali; i layer ammessi sono 1–63 e il blocco MTP
resta escluso. I provider API non possono attivare l'opzione.

Prima di avviare il modello H3 controlla directory, dimensioni, copertura layer,
tipo F32 e valori finiti; rifiuta file incompleti, GLP/projectivi e architetture
diverse. Una copia identificata da SHA256 evita il separatore del disco Windows
nei parametri di llama.cpp. Intensità/file/layer entrano nella chiave di residenza:
cambiarli ricarica il processo gestito alla prossima richiesta. Disattivandolo si
torna al percorso normale, senza cambiare pesi o le altre impostazioni.

Ricerca: UCVG documenta vettori additivi e pubblica esempi di valutazione, ma
nell'albero pubblico e negli allegati delle release esaminati non è stato
trovato un GGUF appropriato per il 27B locale. Gli esempi Qwen3.8 presenti
nell'albero includono il 9B: non sono stati scambiati per vettori del 27B.
Non sono stati sostituiti con file inventati.
I candidati GLP richiedono invece proiezione, non il supporto additivo disponibile
nei motori installati. Non esiste ancora una prova di un vettore sul preciso ISTA
locale: forma compatibile e dichiarazioni dell'autore non bastano a garantirla.
Il lancio con MTP è coperto solo da test simulati; qualità, velocità e accettazione
delle bozze devono ancora essere misurate con un vettore reale appropriato.

## Installazione verificata

Il catalogo locale contiene il modello ISTA-DASLab
`Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf`, 12.120.016.960 byte. Il profilo ottimizzato
H3 lo riconosce come qwen35, 65 layer e dimensione embedding 5120, con MTP.
Al momento della lettura lo LLM selezionato nella chat era invece un provider API:
la presenza del Qwen locale non significa che fosse il modello attivo.

Entrambi gli eseguibili installati sono stati interrogati con il solo `--help`,
senza caricare modelli: motore CUDA standard e motore Qwen27 ottimizzato
`qwen27-mtp-555d1ec-window8k`. Entrambi espongono `--control-vector`,
`--control-vector-scaled` e `--control-vector-layer-range`.

## Cosa è fattibile e cosa manca

Un control vector GGUF separato permette una modifica delle attivazioni durante
l'inferenza, senza riscaricare l'intero modello. Disabilitarlo ripristina il flusso
di base. Non equivale a ricostruire automaticamente una specifica variante
«abliterated»: una trasformazione dei pesi e una modifica runtime delle attivazioni
sono operazioni diverse, da confrontare sperimentalmente.

La sola presenza dei parametri nella guida non prova che il vettore venga applicato
correttamente a ogni blocco di questo modello e alla bozza MTP. Il supporto upstream
per control vector di qwen3.5/qwen-next è stato aggiunto con la PR #20653. Serve una
verifica del ramo concreto, della propagazione al modello principale e del rapporto
con MTP, evitando un aggiornamento indiscriminato del motore ottimizzato.

Non è stato ancora identificato o verificato un vettore specifico per questo
checkpoint ISTA. Non basta che un file abbia «Qwen» nel nome: vanno controllati
modello di origine, architettura, dimensioni, tensori/layer e provenienza.
La trasferibilità fra checkpoint/quantizzazioni non è una garanzia di equivalenza.

Aggiornamento della ricerca: esistono candidati pubblici per il Qwen base, tra cui
GLP-49 (LoRA PEFT 8,6 MB e GGUF projectivi sperimentali da 1–1,3 MB) e una direzione
distribuita per la variante Mirai. Sono checkpoint/formati diversi dall'ISTA locale:
non è stata verificata la loro compatibilità. La pagina GLP-49 richiede inoltre
l'accettazione delle condizioni per accedere ai file; non sono stati scaricati.

La seconda verifica `--help` mostra che entrambi i motori locali hanno `--lora`
e control vector standard, ma non espongono `--cvec-mode`. Il GGUF projectivo dei
candidati non va quindi trattato come un normale vettore additivo: il supporto
generico all'argomento non dimostra il supporto a `glp.mode`. Prima di integrarlo
serve verificare/adattare il runtime o valutare una conversione dell'adapter LoRA,
con prove sull'esatta architettura e sulla quantizzazione ISTA. La sola presenza
di `--lora` non garantisce che l'adapter PEFT sia direttamente caricabile.

## Regole dell'integrazione H3

Opzione sperimentale in Opzioni tecniche LLM, inizialmente disabilitata, salvata
per modello: file vettore locale, intensità e intervallo dei layer. Una selezione
incompatibile produce un errore esplicito prima del caricamento. Il processo e la
cache di residenza includono la ricetta del vettore: cambiare impostazione richiede
un ricaricamento controllato a coda libera, non una modifica dei pesi originali.

Per provider API H3 non può applicare vettori al server remoto; la funzione deve
restare disabilitata, salvo un eventuale supporto specifico fornito dal server.
Le autorizzazioni Agent, l'accesso ai file e i controlli sui tool rimangono controlli
del servizio H3, separati dal comportamento del LLM.

Prima dell'attivazione: confronto controllato senza/con vettore su italiano,
JSON, scelta strumenti, grounding RAG e continuità degli artefatti; memoria,
velocità e qualità vanno misurate, non dedotte dalla piccola dimensione del file.
Prima prova senza MTP, poi con MTP solo dopo aver verificato la compatibilità.
Questa nota non autorizza generazioni di test, download o sostituzione del motore.

## Fonti primarie

- Modello: https://huggingface.co/ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF
- Control vector: https://github.com/ggml-org/llama.cpp/blob/master/tools/cvector-generator/README.md
- Supporto dei modelli: https://github.com/ggml-org/llama.cpp/pull/20653
- Candidato GLP-49, dichiarazioni dell'autore: https://huggingface.co/msuiche/Qwen3.8-27B-abliterated-cyber-GLP-49
- Variante Mirai, documentazione dell'autore: https://huggingface.co/alesha-pro/Qwen3.8-27B-S-mirai-GGUF
- UCVG, formato additivo e limiti dei percorsi Windows: https://github.com/Egor4More/ucvg.cpp

## Controllo finale dei candidati, 27 ottobre 2026

Sono stati verificati anche gli allegati delle release UCVG v0.1/v0.2: contengono
i motori compilati, non un vettore 27B pronto. La variante Mirai richiede
esplicitamente l'operatore projectivo e un motore dedicato; i due eseguibili H3
non espongono quel modo, quindi il file non è stato applicato come additivo.

Il candidato pubblico `com-kotobalabs/Ternary-Bonsai-2-27B-Refusal-Steering-GGUF`
è piccolo e additivo, ma deriva da un altro checkpoint/quantizzazione. Il suo
stesso autore riporta quattro rifiuti su quattro prove fuori campione e collasso
con dosi maggiori. Non fornisce una base verificata per promettere il risultato
richiesto sull'ISTA locale e non è stato installato o attivato.

La scelta di rilascio è mantenere il caricamento manuale sperimentale, spento
per default e con validazione rigorosa. Questa è una limitazione esplicita,
non una conferma di efficacia o di compatibilità di un vettore non provato.

- Candidato e misure dell'autore: https://huggingface.co/com-kotobalabs/Ternary-Bonsai-2-27B-Refusal-Steering-GGUF
