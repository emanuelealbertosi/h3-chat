# Slide AI e voce naturale

Il flusso delle presentazioni resta invariato quando **Illustrazioni AI · tutte insieme**
è disattivato (impostazione iniziale). Documenti, figure RAG e allegati continuano
a essere disponibili al LLM.

## Ricreare una sola pagina

Nel canvas scegli una slide HTML, apri **Ricrea questa slide con AI**, scrivi le
modifiche e premi **Ricrea solo questa slide**. Viene usato il LLM attualmente
selezionato, anche un provider esterno. L’HTML arriva progressivamente nel canvas.
Le altre pagine restano identiche; la presentazione precedente resta nella
cronologia. La nuova versione è modificabile graficamente ed esportabile come
prima. Le fonti RAG già utilizzate e le immagini del deck vengono conservate.

## Illustrazioni opzionali

Quando selezioni **Slide**, puoi attivare **Illustrazioni AI · tutte insieme**
e scegliere un modello immagini disponibile, oppure quello predefinito in admin.
Si usano i suoi parametri di generazione configurati nelle Preferenze.

Il LLM prepara prima la scaletta e un unico piano di immagini. I prompt per Anima
e SDXL usano tag inglesi; gli altri modelli ricevono descrizioni adatte al loro
formato. Il modello immagini genera le illustrazioni consecutivamente, mantenendo
il motore caricato. Poi viene rilasciato e il LLM compone l’HTML utilizzando il
catalogo appena creato, senza alternare modelli per ogni pagina. Questo passaggio
usa la memoria a richiesta anche se la chat normale tiene modelli residenti.

Non è un batch di immagini simultanee sulla GPU: ciascuna viene generata da sola
per contenere la memoria. Il piano può omettere illustrazioni non utili, con al
massimo una per slide. Grafici numerici, formule e diagrammi precisi restano
HTML/SVG. Le illustrazioni generate non vengono presentate come prove documentali.
Per chiedere una figura per ciascuna pagina, scrivi «una immagine per ogni slide»
nel prompt. «Tutte insieme» indica che la generazione avviene in un solo ciclo
di caricamento del modello, non che ogni pagina debba avere una fotografia.
Ogni pagina riceve gli identificativi delle illustrazioni assegnate; se l’HTML
le omette viene richiesta una sola correzione al LLM, senza rigenerare le immagini.
Se vengono ancora omesse, il canvas mostra un avviso sulla pagina interessata.

## Figure entro la pagina

L’HTML mantiene il layout libero del LLM. Se una griglia o un contenitore flex
sborda a causa delle dimensioni minime intrinseche, il visualizzatore rilassa
solo questi vincoli. Le immagini troppo grandi vengono limitate preservandone
le proporzioni; il viewBox dei diagrammi include le etichette fuori dai bordi.
Le stesse correzioni si applicano alle presentazioni già create e agli export.
Non vengono scelti nuovi template o ridotti i caratteri. Se rimane troppo testo
o un altro tipo di sbordamento, resta visibile l’avviso per correggere la pagina.

## Espressività Voice

H3-Chat usa Higgs Audio v3 e il codec Higgs Audio v2, con lo stesso motore di
sintesi adattato da H3-Audio. Il controllo **Espressività**, presente nella chat
e nelle Preferenze, distingue **Naturale · come il campione**, **Sobria** ed
**Espressiva**. La modalità naturale non impone il tag di espressività bassa.
Emozione, velocità, registro e temperatura restano indipendenti. I campioni
determinano identità vocale e pronuncia: per l’italiano usa un riferimento italiano.
