# LongTakeNoCuts · sperimentale

Opzione della singola richiesta, disattivata per i video precedenti e per le
nuove richieste normali. Disponibile nelle impostazioni avanzate del compositore
e nelle finestre **Modifica clip** e **Ricrea video**. In Modifica clip riguarda
soltanto le clip selezionate: per provarla su una sola clip selezionare quella.
Non modifica i preset, non avvia automaticamente rendering e non impone SAM.
Un server già avviato abilita il controllo dopo l'aggiornamento a coda libera.

Il percorso aggiunge cinque passi di rifinitura con denoise 0,55 dopo i passi
base, poi fonde il video latente con una rampa fra i fotogrammi 22 e 44.
L'audio latente rimane quello della generazione base; audio originale,
lip-sync e montaggio della traccia musicale conservano i propri intervalli.
PDD è escluso: l'interfaccia rende esplicita la scelta, il server rifiuta
combinazioni incompatibili. Nessun vantaggio di tempo o memoria è garantito.

È un adattamento del metodo [H3-LongTakeNoCuts](https://github.com/xyzDist/H3-LongTakeNoCuts)
fissato al commit `0cad00ab92e4ad8de3d54ddd5254142bccb702d9`.
La fusione è adattata dal nodo MIT, con licenza e provenienza in
`h3chat/vendor_longtake`. Non carica il workflow ComfyUI o custom node esterni.

## Adattamento alla timeline modificabile

Per le clip successive usa un contesto di movimento di 22 fotogrammi, codificato
dalla coda effettivamente consegnata dalla clip precedente, sul canvas nativo
prima del ritaglio spaziale. Non usa gli eventuali fotogrammi extra della griglia
VAE, che non sono stati mostrati. Salva soltanto sette passi VAE in un piccolo
file safetensors su CPU, senza tenere un video latente completo residente.

Diversamente dal workflow di esempio, il contesto è collocato **prima**
dell'origine della clip con sette guide temporali native firmate. Non c'è una
testa sovrapposta da eliminare: durata, timestamp locali, audio e confini delle
clip restano gli stessi. Questa prima integrazione ricodifica la coda video
nel VAE; non promette il percorso senza ricodifica dei latenti originali.
I controlli CPU verificano le coordinate reali del PackedLayout incluso nel
runtime, comprese le origini invarianti di video e audio.

La regia Storyboard conserva gli stacchi `cut`: ricomincia il contesto a ogni
stacco. Una clip senza contesto precedente avvia un nuovo tratto con rifinitura.
Contesti di modelli/canvas diversi, file mancanti o video modificati vengono
rifiutati e il log indica il nuovo tratto. Nessun contesto viene ridimensionato
silenziosamente. Risoluzione e file del diffusore/VAE fanno parte della firma.

Le versioni mantengono i propri file e metadati. Una modifica locale può usare
il contesto della versione precedente scelta, se compatibile. Non rigenera
automaticamente la clip successiva. La finestra segnala i raccordi che usavano
una vecchia versione del predecessore: l'utente decide se rigenerarli.
Una modifica di un intervallo invalida il contesto dell'intera clip combinata,
evitando di propagare la vecchia coda. Inserimenti prima/dopo mantengono il
proprio percorso di estensione; LongTakeNoCuts non è abilitato in quel percorso.

## Risultati e verifica

`video-plan.json` conserva l'opzione e il risultato `longtake`, con contesto,
rifinitura e audio utilizzati. `longtake-result.json` separa tempo del
campionamento base, tempo di rifinitura e tempi dei cinque passi aggiuntivi.
`sampling_seconds` include entrambi: non sommare di nuovo il tempo di rifinitura.
Maschera `null` significa fusione dell'intero frame, senza segmentazione.

Verificati: scelta esplicita e compatibilità con vecchio server, esclusione PDD,
fusione con tensori reali CPU, audio identico al base, salvataggio/rifiuto dei
contesti, coordinate del runtime, percorso worker completo con modelli simulati,
una sola clip modificata senza rigenerare le vicine e preset invariati.
Non è ancora un collaudo visivo GPU: continuità, deriva, sfondo e costo effettivo
restano da misurare. Il primo collaudo concordato resta Kratos originale completo
a 0,70 MP, da avviare esplicitamente dopo i lavori attuali.
