# Steering LLM — verifica del 26 ottobre 2026

Stato: ricerca tecnica; nessun peso scaricato o cambiato, nessun vettore applicato.

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

## Possibile integrazione H3

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
