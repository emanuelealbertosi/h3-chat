# Ricreare un video con nuovi parametri

Sotto un video MiniMax generato, nella chat e nel canvas, premi **Ricrea video**.
Puoi anche premere **↻ Ricrea video** accanto alla galleria e scegliere un video
generato in un'altra chat della tua area.

La finestra recupera i prompt realmente inviati al motore, i riferimenti per
ogni clip, i fotogrammi guida, il lip-sync, la traccia audio e gli intervalli
originali. Funziona anche su una versione ottenuta con **Modifica clip**.
Puoi consultare le istruzioni recuperate prima di avviare la generazione.

Cambia risoluzione e passi; nei parametri avanzati trovi CFG, sampler,
scheduler, seed, attenzione e offload. Di default vengono conservati i seed
originali di ogni clip. La scelta vale soltanto per questa richiesta: i preset
del modello non cambiano. Il modello resta quello usato nel video originale.

**Ricrea tutto il video** genera una nuova versione con gli stessi clip, tempi
e formato, senza richiedere un nuovo piano all'Assistant. La musica originale
viene rimontata in modo continuo. La richiesta rispetta la coda condivisa;
se viene interrotta, il normale pulsante Rigenera recupera i clip già salvati.
La versione precedente rimane disponibile.

Aumentare la risoluzione richiede più VRAM e tempo e può causare un errore di
memoria. Una nuova generazione può cambiare il risultato visivo anche con lo
stesso seed. Quando la versione precedente contiene modifiche a un intervallo
di un clip, la sua regia combinata viene reinterpretata per l'intero clip;
il filmato mostra un avviso prima del rilancio.

Un MP4 caricato dal PC non contiene le istruzioni e i riferimenti originali:
per il recupero automatico scegli la generazione conservata in H3-Chat. Il
modello locale e i file di riferimento devono essere ancora disponibili.
