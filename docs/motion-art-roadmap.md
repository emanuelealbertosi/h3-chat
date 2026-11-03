# Motion Graphics: asset animabili e scenari

Decisione del proprietario, 1 novembre 2026. Integrare la nuova catena nell'app,
preservando la modalità classica e la selezione esplicita delle raccolte.

## Stato verificato

- Scene strutturate con gruppi, immagini autorizzate, camera e parallasse.
- Raccolta di pose vettoriali/raster, copie indipendenti nel progetto; riuso per scelta.
- Prova reale breve in corso: tre scene originali della scuola, prima Qwen 27B
  IQ3_S locale, poi DeepSeek esterno. Prompt, allegato, ricetta immagini/voce/musica
  conservati in work/motion-art-2026-11-01. Non è una prova di rig articolato.
- Le immagini generate assegnate a una scena sono comunicate al compositore e
  verificate: se vengono ignorate, è richiesta una sola correzione.
- Direzione artistica e significato delle scene vicine arrivano al compositore.
- Anteprima continua nel canvas con le stesse transizioni grafiche dell'export.
- Campioni vocali femminili/maschili, neutri/caldi/vivaci generati realmente.
  Il riferimento maschile italiano sostituisce il vecchio campione spagnolo;
  non dichiarare l'accento perfetto senza ascolto.

## Proposta: da implementare dopo il confronto

1. Pianificazione unica di scene, azioni e inventario, prima di generare asset.
2. Personaggi da riferimento comune: busto, testa/viso, braccia/mani e gambe;
   punti di aggancio, ordine dei livelli e sovrapposizioni alle giunture.
   Generare pezzi scollegati non garantisce anatomia o identità coerenti.
3. Poche azioni collaudate iniziali: saluta, indica, osserva; camminata e presa
   richiedono un rig/pose realmente adatti, non il trascinamento di una PNG.
4. Scenari con fondale, ambiente, oggetti, persone e primo piano; nuvole, sole,
   paesaggi e interni separati dove la regia lo richiede.
5. Titoli decorati e fumetti modificabili, grafici/contatori/infografiche precise
   su livelli separati; eventuale sfocatura/attenuazione applicata solo al fondale.
6. Raccolte con provenienza, stile, palette, personaggio, parti e azioni disponibili.
   Scelte Crea nuovi / Usa raccolta / Misto, anteprima e riuso autorizzato.
   Nessun inserimento automatico di asset non scelti.
7. Generazione di immagini per lotto con un solo caricamento del modello;
   controllo alpha/bordi, giunture, ingombro testi e continuità prima dell'export.

Primo obiettivo: un personaggio articolato e due scenari, verificati prima di
estendere il catalogo. Non presentare questa proposta come funzionalità già pronta.

## Efficienza emersa dalla prova

Il generatore immagini condiviso ricaricava l'LLM dopo il lotto anche quando subito
dopo doveva partire la voce. La correzione evita questo caricamento intermedio
nel percorso infografiche, conservando il percorso slide che compone subito dopo
le immagini. Applicazione prevista dopo entrambi i campioni, a coda libera.

Export CPU: sul renderer locale, 10 acquisizioni 1080p per modalità hanno misurato
216,2 ms medi con PNG standard e 47,5 ms con PNG ottimizzato per velocità. I pixel
decodificati del campione confrontato sono identici. Sono tempi di sola cattura,
non una promessa dello stesso fattore di accelerazione del filmato intero.
Il percorso PNG ottimizzato ha un fallback per renderer precedenti e ha passato
un export reale sintetico a due scene. Applicazione dopo il confronto.

## Difetti visivi osservati nel campione locale

Nelle scene 1 e 3 del job (prova locale) il modello ha
generato scritte con fill:none e nessun contorno: i testi esistono nei dati ma
non vengono dipinti. Registrare questo come difetto reale, conservando l'output
originale. Il controllo mirato per la generazione è scritto e testato: richiede
un colore leggibile oppure un contorno visibile, ammette colori animati e testi
contornati. Attivarlo dopo il confronto per usare lo stesso software nei due test.
Non dichiarare il campione locale visivamente approvato.

Entrambi i modelli hanno omesso il logo originale allegato nel confronto. Per
le nuove generazioni viene assegnato esplicitamente alla prima scena (oppure
all'ultima se chiesto) quando l'utente richiede il logo e vi è un solo allegato
immagine, quindi non c'è ambiguità. Con più immagini non viene indovinata
l'identità del logo. La revisione Motion riceve ora il grafico originale completo,
con verifica del budget di contesto, oltre alla richiesta di modifica.

## Aggiornamento 1 novembre: prima implementazione articolata

Personaggi Articolati e ritmo Rapido sono ora opzionali e attivi localmente.
Il campione diretto (prova locale) dimostra saluto,
indicazione e transizione fra due scenari: 21,24 secondi, 638 frame verificati.
Il campione automatico locale (prova locale) completa
regia, sfondo Qwen, foglio parti Qwen, trasparenza CPU, voce Higgs, composizione
e MP4: 10,34 secondi, 311 frame verificati, 9m38s di elaborazione totale.
La composizione è stata corretta una volta dal modello per la parallasse dei
figli; l'output corretto ha superato i controlli CPU di testi e risorse.

Una prima prova automatica è stata fermata durante lo sviluppo: aveva generato
un foglio chiaro con il solo contorno magenta. Il nuovo controllo lo rifiuta e
il prompt del foglio non eredita più sfondo, font o camera della scena.
La prova corretta è distinta dal montaggio diretto: non attribuire la grafica
composta a mano alla regia automatica. File e verifiche sono in
work/motion-rigs-2026-11-01.

Limiti osservati: stile da marionetta e giunture visibili, appoggio dei piedi
nello scenario ancora poco convincente, nessuna camminata o labiale. La prova
automatica dimostra il collegamento della catena, non una qualità professionale
già raggiunta. Archiviazione nella raccolta solo dopo verifica e conferma.
Nessuna pubblicazione GitHub di queste modifiche ancora eseguita.

## Aggiornamento successivo: tre scelte e percorso continuo 2.5D

L'utente ha scartato la resa delle marionette. L'interfaccia principale distingue
ora Normale, Decorativa e Piano sequenza 2.5D, mantenendo il percorso HTML/SVG
compatibile con video, audio e griglie. L'esperimento articolato resta avanzato
e separato dalla nuova modalità. Nessun preset utente è stato modificato.

Il movimento usa una sola curva temporale con velocità continua, tre piani di
profondità separati e raccordi occultati da un elemento vicino alla camera.
Il vecchio selettore transizioni conserva il valore ma viene disabilitato finché
è attivo il piano sequenza, che applica i propri raccordi. Anteprima completa e
MP4 condividono il codice. È un piano sequenza simulato, non uno spazio 3D.

Prove in work/motion-cinema-2026-11-01:
- campione diretto (prova locale): 21,24s con immagini, voce
  e musica già locali; nessuna nuova diffusione, personaggi rimossi;
- composizione automatica locale (prova locale): 14s senza
  voce o musica, 420 frame completamente decodificati, due immagini assegnate
  correttamente e livelli .35/1/1.65 più HUD0; 3m18s totali;
- browser isolato: passaggio fra tre scelte conserva MP4, sei pannelli, duck;
  preview con dodici istanze video, parallasse distinta e seek deterministico;
- vero export CPU sintetico con sei pannelli video e audio in loop attraverso
  il cambio scena: 40 frame decodificati e audio presente anche dopo il raccordo.

Le verifiche sono distinte: il campione diretto non è una composizione dell'LLM.
Il controllo strutturale dei livelli non certifica qualità artistica o corretta
separazione semantica dei soggetti. Le immagini di base rimangono illustrazioni
piatte, integrate qui con elementi ambientali separati. Da valutare con l'utente
la resa dei raccordi e l'ulteriore generazione di asset ambientali dedicati.
