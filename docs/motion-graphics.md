# Infografiche Motion Graphics · sperimentale

Nelle impostazioni Infografica scegliere **Motion Graphics** in Motore animazione.
Classico resta il valore predefinito e conserva i progetti HTML/SVG esistenti.
La nuova modalità usa una scena libera: gruppi, livelli, forme, testi, immagini
autorizzate, barre, contatori e camera hanno keyframe modificabili. Le indicazioni
del prompt prevalgono; allegati e fonti RAG selezionati restano nel contesto.

Il modello produce esclusivamente dati JSON validati. Nessun JavaScript generato
viene eseguito. Lo stesso valutatore temporale produce anteprima, seek e MP4:
i keyframe della versione2 non vengono compressi o troncati come nodi legacy.
La camera supporta pan/zoom; `parallax` dei gruppi principali varia da0 a2.
I grafici numerici restano deterministici; dati inventati per una dimostrazione
devono essere esplicitamente indicati come illustrativi.

Nel canvas si possono scegliere oggetto/camera, modificare tempi, valori, curve,
livelli e parallasse, annullare/ripetere modifiche locali e salvarle. Poi
**Esporta / aggiorna MP4** usa il progetto e gli audio esistenti senza nuove
chiamate LLM/TTS. Le modifiche locali vanno salvate prima di cambiare pagina.

La voce viene generata prima della scena. Le durate sono misurate sull'audio;
i cue disponibili per frase vengono passati al pianificatore. I movimenti
interni restano una regia stimata: nessuna pretesa di allineamento per parola.
Senza voce la durata è manuale. Il progetto memorizza esplicitamente questa
distinzione.

## Sprite riutilizzabili, solo per scelta

La raccolta è privata per account e separata dai progetti. Dal canvas selezionare
un gruppo e **Salva gruppo come sprite**. Viene conservata la posa corrente:
nome, descrizione del soggetto, stile e tag devono essere controllati e confermati
prima del salvataggio. I colori vengono ricavati dai dati della grafica.
Non è una descrizione Vision automatica né una promessa di riconoscimento
semantico infallibile. Si cercano nome, descrizione, stile, tag e colori.

In impostazioni usare **Raccolta sprite** per visualizzare e scegliere quelli
adatti. Nessun elemento viene riutilizzato automaticamente. Le istanze sono
copie dei dati originali espanse nel progetto: eliminare un elemento dalla
raccolta non modifica i progetti già salvati.

La raccolta supporta sprite vettoriali e immagini raster già presenti nel progetto.
Le immagini vengono copiate in un archivio condiviso con nomi basati sul contenuto,
così rimuovere l’allegato originale non elimina la copia dello sprite. Eliminare
lo sprite rimuove la voce e i dati della raccolta; le immagini condivise rimangono
per non rompere i progetti salvati. La caption Vision automatica opzionale resta
un’estensione futura: le descrizioni attuali sono confermate dall’utente.

## Limiti della prima versione

- Scene con massimo256 oggetti,4096 keyframe e512000 byte; errore esplicito se
  il budget viene superato, senza scarti silenziosi.
- Al massimo12 immagini distinte per scena,16MiB ciascuna e64MiB complessivi.
  Le immagini vengono decodificate prima del rendering. Un controllo CPU
  misura l'ingombro dei testi e segnala quelli fuori dal viewport anche con
  la camera, chiedendo al modello una sola correzione mirata.
- Da1 a30 scene e massimo600 secondi, come il motore classico.
- Forme SVG strutturate e gruppi; non ancora importazione generica di SVG esterni,
  rig completo di personaggi, maschere/filtri avanzati o curve personalizzate.
- Video di sfondo, split screen e raccolte sfondi restano nella modalità classica.
- La qualità di una composizione generata richiede verifica visiva. Demo scritte
  a mano, test con provider simulato e generazioni reali sono prove distinte.

La prova P0 esporta10 secondi1080p30fps e verifica300 fotogrammi decodificati;
la demo dati-centri P1 usa tre scene originali senza copiare il video indicato.
