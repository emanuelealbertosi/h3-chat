# Varianti video e montaggi alternativi

Nelle impostazioni Video della chat, **Varianti per clip** sceglie da 1 a 8
generazioni per ogni clip. È disponibile dal primo invio: testo, immagini di
riferimento, I2V, video da modificare, musica e filmati a più scene. Lo stesso
controllo è nelle preferenze del modello, nella modifica della timeline,
nell’aggiunta di una clip e in Ricrea video. Il valore iniziale è 1.

Il prompt può prevalere con `3 varianti per clip` o
`3 versioni dell’intero video`. Un numero di inquadrature dentro una clip non
cambia il numero di generazioni. Il numero di varianti non cambia la durata,
la risoluzione, i riferimenti o la canzone.

- **Alternative per clip**: tutte le alternative ricevono lo stesso contesto
  precedente selezionato. Il primo montaggio usa la variante 1. Le altre sono
  disponibili nel ventaglio sopra la timeline per un montaggio libero.
- **Versioni complete**: ogni ramo riceve apertura e finali delle proprie clip
  precedenti; una variante non eredita la memoria nativa dell’ultima alternativa
  appena generata. Sono salvati anche i montaggi completi per ogni ramo.
  Il selettore sopra la timeline sceglie una versione su tutte le clip disponibili.
  Le clip non rigenerate restano nelle versioni già scelte.

La pianificazione è condivisa: il batch non richiama l’Assistant per ogni take.
Le generazioni sono sequenziali, con la normale gestione del modello caricato.
Un seed fisso diventa seed base, base+1, base+2, ecc.; con seed casuale viene
estratta una base per clip, salvata prima della generazione. Nei dettagli di ogni
variante resta il seed effettivo. Tre varianti costano circa tre volte tempo e
spazio di una singola generazione; non vengono eseguite insieme sulla GPU.

Ogni take completato è registrato immediatamente in un journal separato. Se
si interrompe la generazione, la ripresa riutilizza i take già pronti della
stessa ricetta e genera soltanto quelli mancanti. Non è un rilancio automatico:
lo stop umano rimane rispettato. Non riusare un journal con prompt, riferimenti,
durata o parametri diversi.

Le alternative a una modifica parziale sono tutte ricomposte contro la stessa
versione sorgente e salvate in file distinti. Le clip brevi generate senza
canzone hanno una timeline propria; scegliendo un take si sceglie anche il suo
audio generato. Con una canzone fornita, tutte le varianti conservano il medesimo
segmento originale. Cambiare una variante non garantisce un raccordo perfetto
con la clip successiva: la memoria è una condizione generativa.

I test automatici usano motori simulati e composizione CPU. La qualità e il
comportamento del modello su GPU vanno verificati sul primo batch reale; non
vengono dedotti dall’esito dei test.
