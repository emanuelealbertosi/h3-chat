# Mappa delle funzioni H3-Chat

Questo indice instrada ai documenti mantenuti nel repository. Leggi il documento della modalità usata, non l'intera lista. Se una funzione non coincide con il server installato, controlla codice e versione attiva prima di rispondere o cambiare impostazioni.

## Chat, progetti, RAG e provider

- `docs/composer.md`: controlli Automatico, Immagini, Music, Video, Voice, Slide, Manim, Calcolo, Trascrivi; Web/RAG/Assistant indipendenti; canvas e sidebar.
- `docs/chat-tools.md`, `docs/projects-and-animations.md`: progetti, documenti, fonti, indicizzazione, Vision, strumenti numerici e Manim. Gli allegati non equivalgono al RAG; il RAG può caricare un encoder anche con Assistant Off.
- `docs/api-providers.md`, `docs/external-servers.md`, `docs/access.md`: provider LLM esterni, server media e accessi/workspace. Chiavi protette: non stamparle. Cambiare LLM non deve cambiare il modello immagini implicitamente.
- `docs/llm-acceleration.md`, `docs/mtp.md`: contesto, cache, MTP e memoria. Non interpretare un grafico Windows '3D' basso come prova che CUDA non lavori; correlare log, passi e misure.

## Immagini, modelli e seed

`docs/vision-engine.md`, `docs/images-and-loras.md`, `docs/image-recipes.md`, `docs/moss-image.md`, `docs/krea2.md`, `docs/lora-library.md`, `docs/upscale.md`.

Modello, formato, megapixel, sampler/scheduler, passi, CFG, negativo e seed sono impostazioni del modello e della chat; i parametri espliciti nel prompt hanno priorità dove supportati. MOSS distingue INT8/BF16 o checkpoint diversi: non basta il nome generico se ci sono più scelte. Usa i nomi/ID reali del catalogo. Non trasferire sampler e parametri incompatibili fra modelli. 'Riusa impostazioni' recupera una ricetta, non è un lancio; 'Usa ultimo seed' recupera il seed risolto. Cambiare modello o quantizzazione non garantisce la stessa immagine.

MOSS accetta testo naturale con Assistant Off. Con Assistant On il percorso spaziale può tradurre posizioni nel layout JSON ufficiale: leggere `docs/moss-image.md` prima di costruirlo. La griglia interna può richiedere padding e crop: non ridurre silenziosamente i megapixel richiesti per farli entrare in un vecchio limite. Leggere dimensioni del risultato effettivo.

I LoRA vanno abbinati alla famiglia e al modello; controllare metadati, struttura e tensori realmente applicati. Un file .safetensors allegato non è un'immagine. Non assumere che un peso di influenza 1 sia una misura della memoria occupata.

## Lotti immagini

`docs/image-batch.md`, `h3chat/image_batch.py`, `h3chat/image_batch_controls.py`.

Un piano Assistant per tutto il lotto; modelli raggruppati per riutilizzo, presentazione nell'ordine richiesto. Senza modello/parametri espliciti si usano le scelte salvate per il modello corretto, non settaggi inventati dal planner. Riferimenti per voce: 'senza allegati' deve rimanere senza immagini. Seed fisso o casuale per voce. Chat e canvas mostrano un'unica risposta con immagine principale e miniature. Ogni risultato completo si salva subito; non promettere ripresa automatica di un lotto immagini interrotto.

## Music, Re-sing, Voice e Remix

`docs/music-engine.md`, `docs/music-engines-resing.md`, `docs/music-quality.md`, `docs/voice-and-soundtracks.md`, `docs/voice-quality.md`, `docs/video-remix.md`.

Music cambia pannello secondo YuE2 o MiniMax Music 3. Re-sing richiede il percorso YuE2 locale, una canzone da 3s a 5min, separazione e allineamento della voce. Testo nelle impostazioni ha priorità; se manca, l'Assistant scrive il testo dal prompt anche con Assistant Off e serve un LLM. Non confondere nuovo brano MiniMax con ricanto sulla base originale. Verificare effettivo allineamento e ascoltare prima di approvare qualità.

Voice usa Higgs e può accompagnare Manim, slide, infografiche e video. La durata della canzone è quella decodificata; dodici clip da 15s non coprono una canzone da cinque minuti.

## Slide, infografiche, animazioni

`docs/slides.md`, `docs/slide-ai.md`, `docs/infographics-and-gallery.md`, `docs/infographic-text.md`, `docs/animate-presentation.md`, `docs/infographic-video.md` se presente, `docs/infographic-*.md` esistenti.

Distinguere HTML libero LLM dal motore deterministico. Stile giocoso/fumettoso è disponibile; le illustrazioni AI sono una fase separata e opzionale, con modello configurabile. Il prompt può specificare stile e colori. Nelle slide, non chiedere testo dentro illustrazioni AI per sostituire titoli/sottotitoli HTML; questo causava testi illeggibili. Ricrea singola pagina conserva le altre, fonti e immagini. Controllare sovrapposizione sottotitoli, ritaglio immagini e fonti davvero disponibili. Qwen era la preferenza dell'utente per slide/infografiche: rileggere la configurazione attuale, non imporre un cambio globale.

Nel canvas verificare il risultato reale; animazioni statiche e output del planner non sono un video già renderizzato. Per creazione di artefatti didattici esterni all'app applicare anche le eventuali skill specifiche richieste, senza sostituire il motore H3 scelto dall'utente.

## Galleria, file, metadati e client esterni

`docs/infographics-and-gallery.md`, `docs/uploads.md`, `docs/sillytavern.md`, `docs/build.md`.

La galleria separa asset, timeline, provenienza e account; ha filtri e ordinamento, selezione multipla e cancellazione con scelta esplicita se rimuovere anche dal filesystem. Non cancellare file condivisi o pesi perché un asset viene nascosto. I frame interni delle guide non devono affollare la galleria ordinaria. Seed/ricette possono essere nei dati H3 e nei checkpoint: non garantire che qualunque vecchio PNG/MP4 abbia tutti i metadati incorporati. Verificare prima di proporre una ricostruzione identica.

Il server immagini locale per SillyTavern è documentato in `docs/sillytavern.md`: launcher `Avvia-server-immagini.bat`, adapter compatibile A1111, scelta del modello reale (inclusi MOSS e Anima) e modello residente secondo la politica di memoria. Porta e modelli attivi vanno riletti: non esporre il servizio in LAN/Internet quando l'utente ha chiesto soltanto localhost. Non ripristinare o creare un server separato ComfyUI senza motivo.
