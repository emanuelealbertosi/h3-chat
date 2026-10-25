# Slide AI e voce naturale

## Crea soltanto sfondi

Accanto a **Impostazioni Slide** trovi **Crea sfondi**, con una finestra separata.
Scegli cornici con centro libero o sfondi tenui, formato, modello immagini,
temi aggiuntivi, palette e varianti. **Usa modalità sfondi** seleziona il prossimo
invio: scrivi il tema principale nel prompt e premi **Invia**. Parte soltanto il
batch degli sfondi, senza pianificare slide e senza usare Assistant, RAG o allegati.
**Torna alle slide** ripristina il normale invio; le impostazioni delle slide
non vengono cambiate. La modalità sfondi non viene riattivata automaticamente
ricaricando la pagina.

Il totale è temi × palette × varianti, fino a **24 sfondi** per richiesta.
Le immagini vengono generate in sequenza con il modello selezionato; passi,
sampler e scheduler seguono le sue impostazioni. I megapixel possono essere
lasciati vuoti per conservarne il valore. Il seed può seguire il modello, essere
casuale per immagine oppure fisso per tutto il set. Prompt, modello, parametri
effettivi e seed vengono conservati con le immagini.
Formato, megapixel e parametri di generazione espliciti nel prompt principale
prevalgono sui valori della modale per tutte le immagini del batch. Il numero
degli sfondi resta quello calcolato da temi, palette e varianti nella modale.

Chat e canvas mostrano una **griglia di miniature, quattro per riga** (due sugli
schermi piccoli), aggiornata dopo ogni immagine completata. Clicca una miniatura
per aprire lo zoom e scaricare l’originale. Stop conserva gli sfondi già pronti
in chat, canvas, galleria e nella raccolta dei set.

La **Raccolta sfondi salvati** nella stessa finestra permette di ritrovare gli
originali e recuperare la ricetta del set, anche in un’altra chat dello stesso
account. **Riusa ricetta del set** compila le opzioni e il prompt ma non invia
automaticamente una nuova generazione. La raccolta è separata per workspace.

Margine del centro libero, base chiara/scura e intensità consigliata sono
conservati per il futuro uso nei layout. La simulazione di leggibilità aggiunge
una velatura e un’area testo soltanto all’anteprima; non altera l’immagine né
produce una trasparenza alfa. La posizione degli ornamenti è una richiesta al
modello, non una maschera geometrica garantita. Creare un batch non applica gli
sfondi a una presentazione: il loro uso si sceglie separatamente nelle impostazioni.

Richiede la normale modalità GPU e un modello immagini pronto (anche un servizio
esterno). Nella modalità CPU si può consultare la raccolta ma non generare.
Se il server è ancora alla versione precedente, il pulsante indica di riavviare
H3-Chat dopo la fine di tutti i lavori per attivare la nuova funzione.

## Usare gli sfondi in slide e infografiche

Nelle rispettive impostazioni, **Composizione dello sfondo** offre:
**Automatico** (mantiene il comportamento precedente), **Plain** (tinta unita),
**Gradient** (sfumatura) e **Raccolta**. **Decoration** aggiunge bordi e accenti
HTML/SVG, combinabili con ciascuna base. Non genera nuove immagini. Raccolta
parte senza decorazioni aggiuntive per evitare doppie cornici.

Con Raccolta scegli il batch, spunta gli sfondi e cambia l’ordine con le frecce;
le miniature si possono ingrandire. La sequenza ruota nelle pagine/scene:
tre sfondi su cinque pagine producono 1, 2, 3, 1, 2. L’assegnazione effettiva è
salvata per pagina e rimane nella ricreazione di una singola slide e nella ripresa
delle mancanti. Nessuna nuova generazione immagini è necessaria, anche in modalità
CPU. File mancanti provocano un errore esplicito invece di una sostituzione.

L’intensità regola il contributo dell’immagine; la velatura chiara/scura protegge
la lettura. Le cornici vengono mantenute intere, senza ritaglio, con un’area
interna per i contenuti calcolata sul margine salvato. Il modello riceve le misure
utili per comporre la pagina. La stessa composizione è conservata negli export;
in PowerPoint il fondale è un elemento grafico dietro ai testi modificabili.

Le impostazioni delle infografiche sono indipendenti da quelle delle slide.
Uno sfondo statico selezionato sostituisce il video di sfondo; tornando a
Automatico si riutilizzano i controlli video precedenti. La composizione statica
è mantenuta anche nel rendering offline del filmato e nei layout a riquadri.

## Stile della presentazione

Lo stile selezionato guida sia l'HTML libero sia le illustrazioni AI:

- **Serio / professionale**: grafica editoriale sobria, palette misurata,
  allineamenti precisi e illustrazioni raffinate.
- **Giocoso / colorato**: colori vivaci coordinati, forme morbide o organiche,
  titoli espressivi, composizioni dinamiche e illustrazioni immaginative.
- **Fumettoso**: contorni a inchiostro, campiture, ombre grafiche e accenti da fumetto.

Il LLM sceglie palette, font e impaginazione concrete nella scaletta, poi applica
questa direzione a ogni pagina e al piano immagini. Non viene imposto un template.
Anche la ricreazione di una singola pagina riceve lo stile del deck. Le preferenze
esplicite nel prompt (per esempio fotografie o una palette precisa) restano valide.
Figure originali da PC e RAG non vengono ridisegnate. Per applicare lo stile alle
immagini già generate occorre una nuova generazione: la modifica di una singola
slide conserva le immagini esistenti.

Il flusso delle presentazioni resta invariato quando **Illustrazioni AI · tutte insieme**
è disattivato (impostazione iniziale). Documenti, figure RAG e allegati continuano
a essere disponibili al LLM.

## Sfondo, colore dei testi e palette

In **Slide → Impostazioni** trovi pulsanti separati per **Sfondo**, **Testi** e **Palette**.
Le tre scelte partono da **Automatico**: il comportamento precedente resta invariato.
Puoi scegliere sfondo chiaro, scuro o personalizzato con il selettore colore,
e palette naturale, pastello, vivace, neon o monocromatica. Il LLM riceve queste
preferenze nella scaletta, in ogni pagina HTML e nel piano delle illustrazioni;
continua a comporre liberamente il layout. Le istruzioni esplicite nel prompt
prevalgono sui selettori. Viene richiesto contrasto leggibile fra sfondo e testo.

**Testi** permette Automatici, Chiari o Scuri, indipendentemente dalla palette.
La scelta si conserva nella presentazione e nelle modifiche. Il prompt corrente
prevale, ad esempio «testi scuri». Il controllo di contrasto del canvas considera
anche i gradienti: corregge il testo chiaro su superfici chiare. Quando forzi testi
chiari su fondo chiaro (o il contrario), usa una superficie locale contrastante
dietro le scritte, mantenendo lo sfondo generale e i colori decorativi separati.
Anche le etichette SVG ricevono la scelta del testo. L’export usa il risultato
leggibile del canvas.

Le scelte vengono salvate nel deck e riutilizzate nella ricreazione di una sola
slide; non modificano retroattivamente le altre pagine. Questi controlli sono
disponibili per **LLM · HTML libero**; il motore deterministico conserva i suoi
temi. Le impostazioni delle infografiche restano separate.

## Correzione delle scene statiche

Una scena video deve contenere animazioni interpretate dal motore. Se il LLM
restituisce HTML statico anche dopo la correzione della pagina, viene richiesto
un piano di regia JSON: il modello sceglie gli elementi già presenti, gli
effetti e i tempi. H3-Chat verifica target e durata e applica soltanto gli
attributi di animazione all'HTML originale. Non sostituisce il layout con un
template e non modifica testi, immagini, video, narrazione o musica.

Il canvas riceve la pagina animata, mai il JSON di lavoro. Il piano può essere
corretto una volta; errori del provider e interruzioni dell'utente non vengono
ritentati. Questa correzione funziona anche nella ricreazione di singole scene.

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
Prima di un batch locale vengono chiusi i motori precedenti, compreso il LLM.
Ming e Qwen Image conservano i pesi in RAM tra le immagini, ma rilasciano dalla
GPU i componenti dopo ciascuna fase (encoder, diffusore, VAE): il calcolo resta
su CUDA quando è selezionata la GPU. Questo evita di lasciare pesi inattivi a
competere con le attivazioni o di forzare memoria condivisa di Windows.
Finito il batch, il processo immagini viene chiuso e il LLM viene ripristinato
con contesto, layer GPU, MTP e accelerazione originali, senza ridurne i parametri.
Le immagini su server esterno non richiedono di scaricare il LLM locale.

Il piano completo viene raccolto in gruppi di pagine dimensionati sul limite
**Max token istruzioni immagini** del LLM, distinto da **Max token di risposta**.
Con 2.200 token, per esempio, 15 pagine vengono pianificate in gruppi di 6, 6 e 3.
Se una risposta è troncata, il gruppo viene suddiviso prima di tentare nuovamente;
una singola pagina ha al massimo due tentativi. Si mantengono numeri globali,
scaletta completa e direzione artistica. Tutta la pianificazione deve completarsi
prima di scaricare il LLM o generare immagini: il batch del modello immagini
resta unico. Questo vale anche per le immagini delle infografiche. I valori
salvati di contesto e token non vengono aumentati automaticamente.
Durante la generazione Ming / Qwen Image viene mostrato anche il tempo
dell'ultimo passo, per distinguere il caricamento dal calcolo effettivo.

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
