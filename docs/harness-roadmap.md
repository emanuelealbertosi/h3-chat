# Modalità Agent / Harness — proposta, 25 ottobre 2026

Obiettivo: una modalità opzionale nella chat, richiamabile anche con `agent: …`,
che pianifica, usa strumenti H3, osserva i risultati e corregge il lavoro.
La prima modalità Agent è ora implementata in forma sperimentale: vedi [Guida Agent](agent.md).
File e comandi Windows con H3/Sandbox/Globale sono implementati in forma sperimentale: vedi agent-computer.md. Terminali persistenti, browser grafico e plugin restano fasi separate.

## Riutilizzo di DeepSeek Harness

Il [repository ufficiale](https://github.com/deepseek-ai/deepseek-harness)
è in developer preview e avverte di possibili cambiamenti incompatibili.
Il progetto usa TypeScript/Node e l'architettura Cordis a plugin.
La [licenza MIT](https://github.com/deepseek-ai/deepseek-harness/blob/master/LICENSE)
permette riuso e modifiche mantenendo avvisi di copyright/licenza; le dipendenze
e i contenuti di terzi vanno verificati separatamente prima della distribuzione.
La [presentazione ufficiale](https://www.deepseek.com/en/harness/) mostra agent
loop, strumenti, skill, plugin e controlli; alcune funzionalità sono sperimentali.

Per il primo traguardo si usa un coordinatore Python collegato ai servizi H3, senza
incorporare codice o avviare il runtime DeepSeek. Rimane da valutare il runtime
ufficiale come processo separato, con revisione
fissata e adattatore H3, mantenendo la nostra interfaccia. Evitare un fork dell'intera
app desktop: moltiplicherebbe aggiornamenti e problemi di distribuzione.
Prima del riuso serve una prova del contratto plugin/runtime, dei provider e del
ciclo di vita su Windows e macOS. Il riuso non rende automaticamente sicuro un tool.

## Primo traguardo: agente dentro H3

- Modalità Agent esplicita; il testo normale mantiene il funzionamento attuale.
- Un agente e un modello scelto, con verifica del supporto effettivo agli strumenti.
  Le API esterne e i modelli locali devono rispettare lo stesso contratto; i piccoli
  modelli non vanno dichiarati compatibili senza test.
- Strumenti con schema: ricerca RAG, elenco/lettura degli artefatti autorizzati,
  creazione/modifica slide, pianificazione lotti, lettura stato e risultati.
- La generazione usa la coda H3 esistente, senza caricare modelli GPU aggiuntivi.
  Nessun accesso diretto del runtime al database o alle credenziali dei provider.
- Pannello nella chat con piano, passaggio corrente, strumenti chiamati, esito,
  consumi e pulsanti Stop/Riprendi. Risultati negli stessi artefatti e nel canvas.
- Skill H3 versionate e limitate agli strumenti disponibili; installare una skill
  non concede nuovi permessi. Allegati, pagine web e RAG restano dati non fidati.

Il ponte identifica workspace, chat, utente, run e autorizzazioni con una sessione
limitata. Non espone la chiave generale delle API locali al modello.

## Controlli necessari già nel primo traguardo

Limiti configurabili di passi, tempo, token e costo; arresto propagato agli strumenti;
richieste di approvazione concrete per operazioni non già autorizzate; registro
persistente senza segreti. Un rifiuto o uno Stop non può essere reinterpretato come
permesso di riprovare. Il consenso non si ricava dal testo di documenti o skill.

Ogni azione che avvia un job ha una chiave idempotente e un checkpoint scritto prima
dell'invio. Se la risposta si perde, si riconcilia il job esistente: non si invia di
nuovo. Ripresa della sessione e riavvio dell'app recuperano lo stesso run. I controlli
di permesso si applicano nel servizio H3, non soltanto nel prompt dell'agente.

## Secondo traguardo: file e strumenti esterni

La proposta concreta per cartelle, browser e desktop è in
[Agent e computer](agent-computer.md). È una progettazione separata: nessun
controllo del PC viene abilitato dalla sola modalità Agent già installata.

Solo dopo il primo traguardo: cartelle consentite per workspace, lettura/scrittura
separate, anteprima modifiche, comandi con ambiente e tempi limitati, rete e segreti
isolati. Prima della scrittura verificare i percorsi risolti, inclusi link/junction.
Pubblicazioni, messaggi esterni, cancellazioni e installazioni hanno autorizzazioni
distinte. Non abilitare un terminale senza limiti per imitare una demo.

## Terzo traguardo: estensioni

Gestione plugin/skill, MCP, automazioni e agenti multipli dopo aver stabilizzato
contratti, policy, aggiornamenti e distribuzione. Le automazioni devono conservare
scopo e permessi originali; i plugin di terzi richiedono provenienza e isolamento.

## Prove di accettazione

1. Compito con RAG → piano → artefatto → revisione, con strumenti simulati e poi
   una prova reale autorizzata; stato e costi visibili.
2. Stop durante attesa o tool attivo; nessun invio successivo o rilancio autonomo.
3. Caduta dopo un POST: ripresa senza duplicare il job.
4. RAG ostile e tool che propone un percorso esterno: permessi invariati e accesso negato.
5. Stesso isolamento tra workspace di H3; nessun segreto nel prompt o nei log.
6. Installazione e aggiornamento su Windows e macOS Apple Silicon, anche CPU/API.

È un progetto significativo, ma H3 possiede già coda, canvas, RAG, modelli e artefatti.
Il primo traguardo può restare una funzione circoscritta; l'agente generale per file,
terminale e plugin è una seconda fase più grande. Non è stato installato un runtime DeepSeek aggiuntivo; la modalità Agent locale usa
le dipendenze e il sistema di modelli già disponibili.
