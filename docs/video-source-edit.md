# Modifica video con MiniMax H3

**Modifica video** passes the actual selected source-video interval to H3,
not just its first frame. It uses the existing local MiniMax reference/hybrid
model, video VAE and Qwen encoder; no external H3 app or second video model.
Results depend on the checkpoint: changes are generative and cannot guarantee
pixel-identical preservation outside the requested attributes.

## From chat

1. Choose **Modifica video**, attach a video and optional reference images.
   Alternatively choose the source from the gallery or PC after Send.
2. Write the requested change, for example:
   `Sostituisci la ragazza con quella nell'immagine 1. Mantieni abbigliamento,
   sfondo, movimenti, inquadratura e stacchi originali.`
3. Click a segment in the horizontal timeline to select it and open its editor.
   The checkboxes select multiple clips for generation, while only one editor
   stays open. **Solo un tratto** reveals frame-accurate handles, start/end
   fields and interval playback. Switching clips preserves prompts and ranges.
   The initial chat prompt and images are reused. **Stessa modifica su più clip**
   contains **Applica a tutte le clip**; each text can be adjusted separately.
   **Seleziona tutti** selects the eligible clips without replacing existing
   prompts or version choices. **Deseleziona tutte** clears the selection.
   The batch panel can copy the open clip's image references and mode together
   with the common prompt, so one character image can serve every selected clip.
4. Leave **Rimonta nel video** on for the full film, or disable it for separate
   edited excerpts. The source audio, timeline and aspect ratio are preserved
   by the existing deterministic assembly path.

New imports keep frame-exact boundaries and a minimum of one second per clip.
If the final remainder is shorter, its missing frames are borrowed from the
preceding clip: every original frame and the soundtrack timing are preserved.
Old saved timelines retain their boundaries and versions; an existing tail
under one second stays in the final assembly without being selected for AI
generation. Fractional endpoints are displayed in the timeline.

The same mode is available through **Modifica clip** on generated videos and
external gallery assets. Attribute edits (outfit, background, props, colors)
can use only text. A reference image helps define a replacement person/object.

For an external video, choose **10 secondi** or **15 secondi** before selecting
clips, either in the file/gallery chooser or above the timeline. The default
is 15 seconds. Ten-second windows leave more room for higher resolution but
produce more clips. Each layout has separate cached previews and source
intervals; the final remainder preserves the exact duration. A working timeline
keeps its saved segmentation when reopened. Saved edits are never repartitioned
or overwritten when choosing a different layout on the original upload.

External video import has no fixed ten-minute duration limit. It accepts
readable footage of at least one second and partitions the complete duration
into the selected 10/15-second windows. Thumbnail/audio preparation timeouts
scale with the source duration. Longer footage increases import/assembly time,
disk usage and the number of segments, while GPU editing still processes only
the selected intervals.

The editing, recreation and audio-remix dialogs use a wider layout, one scrolling
surface and a fixed action footer. On narrow screens their columns stack. Remix
keeps the source preview and interval beside the audio controls on desktop.

## Three distinct modes

- **Modifica video**: the complete interval becomes `<Video 1>`. Optional
  pictures transfer only the requested attributes; they do not fix frame zero.
- **Rigenera · riferimenti**: a new scene from the selected images and prompt.
- **I2V · immagine iniziale**: animate a selected initial still.

Assistant On prepares the source-edit relationship and preservation instructions;
it must not invent new camera moves or actions. Assistant Off sends the user's
instructions with the source-preservation contract. Original soundtrack offsets
and reference-image roles are enforced independently of Assistant's output.

## Source conditioning and memory

Each selected interval is 1–15 seconds. The decoder seeks the correct source
time, reads its frames at 24 fps and encodes them as a real H3 video reference.
Qwen receives timestamped source frames at 2 fps, as in the native reference
pipeline. Images, video and audio keep independent Picture/Video/Audio labels.

The source guide is capped at **0.35 MP** by default and never upscaled;
**Dettaglio del video sorgente** allows 0.1–0.98 MP per request. Output resolution
is independent. Aspect is preserved with padding to the latent grid. Temporal
padding repeats only tail frames needed by H3's 17k+5 grid, without discarding
the source ending. Full-video references increase memory and processing time.

Requests use the shared queue and ordinary Stop/recovery. No saved preset is
changed. The saved `source_video_recipe` retains the relative source path and
exact offset/count for **Ricrea video**; missing sources fail explicitly.

API: existing `POST /api/chats/{chat}/video-edit`, with each selected patch
containing `mode: "video"`, optional `reference_megapixels`, optional image
indices and optional `start`/`end`. Arbitrary filesystem paths are not accepted
from the client. The source is resolved in the authenticated user's workspace.

## Guide frames for source edits

**Fotogrammi guida** offers **Inizio**, **Inizio e fine**, or **Inizio · metà · fine**.
Each point can use its original source frame or a selected edited image. When
changing an outfit, edit the guide images consistently; an original guide also
preserves the original clothing at that point. The video still guides the motion.
For adjoining segments, the same edited boundary image can be selected as the
first segment's ending and the next segment's beginning.

These are learned H3 keyframe conditions, not pixel clamps or guarantees of
unchanged motion. Times are relative to the selected interval, including partial
edits: frame 0, frame count divided by two (rounded down), and the last actual
frame. At 15 seconds / 24 fps these are 0, 180 and 359; temporal padding is never
used as an ending anchor. Edited images override the source anchor at that time.
Audio and the other timeline clips remain unchanged.

Guide-video resolution is separate from guide-image and output resolution.
H3 keyframes share the target's spatial latent grid, so lowering the source
video to 0.15 MP does not lower the resolution of those images or the result.
It lowers the detail available between the anchored moments. Combining source
video and several full-resolution keyframes adds memory pressure, so source
detail may need to be reduced on a 16 GB GPU even when output resolution is
unchanged. No saved generation preset is reduced automatically.

API patches accept `anchors: "first" | "ends" | "three"` and `anchor_images`
mapping `first`, `middle`, `last` to manifest image indices. Only positions enabled
by the selected mode are accepted. The older `anchor_image` means `first`.

## Clip versions

The focused clip has a **Versione dello spezzone** selector and preview. Its
selection is used both as the source of the next edit and for **Monta video
completo**. Other alternatives and the original remain saved. Partial edits
save a version of the entire clip, including its unchanged surrounding footage.
Choosing versions and assembling uses saved files, without generating them again.

Completed edits of the same original in the same chat are discoverable even
when they were made on separate branches. Older whole-clip exports are also
included; older partial exports require their **Riprendi timeline** recovery.
Versions from other chats are never accepted. API requests accept a `versions`
object mapping one-based clip numbers (string keys) to IDs from the manifest.
The server resolves the saved source paths, offsets, prompts and reference IDs.

Reference specification:
https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_ref_en.md

## Guide modificate automaticamente

In **Modifica clip → Modifica video → Fotogrammi guida**, attiva
**Modifica automaticamente i fotogrammi guida** e scegli il modello di modifica
immagini. L'opzione è disattivata per impostazione iniziale. Usa lo stesso prompt
della clip; non devi preparare o caricare manualmente i fotogrammi modificati.

Quando attivi l'opzione sono selezionati **inizio, metà e fine**. Puoi scegliere
anche il solo inizio oppure inizio e fine. Se modifichi soltanto un tratto, i
fotogrammi sono calcolati dentro quel tratto e nella versione della timeline
selezionata. Eventuali altre immagini selezionate servono come riferimenti per
l'aspetto richiesto; il fotogramma originale occupa uno dei riferimenti supportati
dal modello immagini.

L'app estrae i fotogrammi, applica la modifica mantenendo posa e composizione,
salva le guide in galleria, scarica il modello immagini e carica MiniMax. Prepara
le guide di tutte le clip selezionate prima della fase video. Se il modello
immagini accetta più riferimenti e c'è spazio, usa la prima guida modificata anche
per mantenere lo stesso aspetto nelle successive. Con Assistant On prepara le
istruzioni prima del batch; con Assistant Off usa direttamente il prompt.

Il lavoro resta nella coda condivisa e Stop interrompe anche questa preparazione.
Riprendendo un lavoro interrotto riusa le guide già salvate. I preset dei modelli,
l'audio e l'opzione di rimontaggio non vengono cambiati. La preparazione aggiunge
tempo e le guide migliorano il condizionamento, senza garantire movimenti o
dettagli delle mani identici all'originale.



### Recuperare, audio e tagli

**Ricarica richiesta / Riutilizza** di una post-produzione riapre l’editor con le clip selezionate, i riferimenti scelti, gli intervalli e i parametri di quella richiesta. I fotogrammi interni dell’importazione non diventano allegati nel compositore.

In ogni clip, **Usa l’audio originale come guida per MiniMax** distingue il condizionamento del modello dal montaggio: disattivandolo, il modello non riceve la traccia, mentre il risultato conserva l’audio originale. Attivare lip-sync attiva anche la guida audio; disattivare la guida spegne lip-sync. I piccoli scarti di durata dell’audio importato vengono completati con silenzio, senza cambiare velocità o posizione della traccia.

**Elimina clip dal montaggio**, nella post-produzione dello spezzone, crea tramite coda una nuova versione senza quella clip e senza il suo tratto audio. Le clip rimaste vengono rinumerate. L’originale e le sue versioni restano disponibili. Non è una generazione AI.

I dettagli apribili della generazione distinguono LoRA salvati e LoRA effettivamente applicati. Un LoRA caricato non garantisce che un Assistant descriva correttamente il personaggio: le istruzioni ricevono ora i nomi dei LoRA attivi e una richiesta di non inventare identità o dettagli non forniti.


## Risuddividere un video importato

La modale Modifica clip offre **Nuova durata dei segmenti** (10 o 15 secondi) e **Risuddividi dal video originale**, anche nelle timeline già modificate. Prima di procedere chiede conferma: modifiche, tagli, istruzioni e versioni selezionate non vengono riportati nella nuova timeline. Riparte dal filmato originale importato; i media e le timeline precedenti restano salvati. La bozza del formato di destinazione viene azzerata, mantenendo le impostazioni del modello. La sola risuddivisione usa la preparazione CPU e non avvia generazioni.

Durante risuddivisione e conversione dell’anteprima compatibile è visibile una barra con fase e tempo trascorso. Le percentuali riguardano la fase corrente e derivano dai fotogrammi iniziali preparati o dai timestamp FFmpeg; lettura, attesa e verifica restano indeterminate. L’attivazione del supporto motore attende la fine dei lavori condivisi, incluse le conversioni CPU.

## Lip-sync su tutto il video

Il comando **Lip-sync con l’audio del video su tutte le clip** attiva lip-sync e guida audio in ogni clip della modale, senza richiedere audio esterno. Ogni segmento usa l’intervallo corrispondente della traccia estratta automaticamente dal filmato. La selezione delle clip da generare resta esplicita. **Applica a tutte le clip** copia anche le opzioni audio/lip-sync della clip aperta; il controllo globale indica uno stato misto se una singola clip viene disattivata. Queste impostazioni sono conservate nella bozza. Disattivare il solo lip-sync lascia disponibile la guida audio.

## Se il pulsante di generazione non reagisce

I limiti degli intervalli sono conservati in fotogrammi, senza arrotondare i secondi oltre la durata reale dell'ultima clip. I controlli del tratto parziale vengono esclusi dalla convalida quando si sceglie l'intera clip. Un parametro non valido mostra un errore visibile nella modale, invece di bloccare silenziosamente il modulo.

**Ripristina bozza salvata** resta disattivato se non è stata ancora salvata una bozza per quella suddivisione. Il suggerimento del pulsante lo spiega; il cursore di attesa compare solo durante un'operazione effettiva. Per conservare le impostazioni già preparate prima di aggiornare l'interfaccia, premi **Salva bozza**, attendi la conferma, poi aggiorna la pagina e riapri lo stesso video e la stessa suddivisione.

## Seed delle clip

**Casuale** (-1) estrae un seed diverso per ogni clip generata. **Fisso** usa il numero inserito per tutte le clip selezionate. Il comando **Usa seed della prima clip** copia il seed della versione selezionata della clip 1; se l'originale importato non ha un seed effettivo, usa la prima versione generata disponibile. Se non esiste un seed numerico salvato, il comando non compare. Le scelte di versione e i preset non vengono modificati dal pulsante. Lo stesso seed non garantisce la stessa identità o lo stesso stile su scene differenti.

## Finestra Attività

Il messaggio video in lavorazione offre **Attività · apri log**. La finestra aggiorna automaticamente numero della clip, fase istruzioni/generazione, clip già generate, dettagli del passo, tempo trascorso e passaggi recenti. Le istruzioni Assistant sono distinte dalla generazione dei filmati. Legge solo riepiloghi del lavoro e non mostra prompt né log grezzi del modello. Chiuderla interrompe gli aggiornamenti della finestra, senza fermare il rendering.

## Spezzoni completati prima di Stop

In modalità **solo spezzoni**, ogni clip completata viene esportata con il proprio tratto di audio originale e registrata subito nella galleria. Stop conserva gli export già pronti anche nel messaggio interrotto. Se un export audio fallisce, il video e la timeline restano salvati e la finalizzazione può riprovare senza rigenerare. Le versioni completate di richieste interrotte vengono proposte anche aprendo la timeline originale; la versione selezionata non cambia da sola.

Il seed effettivo è visibile al caricamento nelle tessere della timeline, nel dettaglio della clip e in ogni versione del ventaglio. Cambiando versione si aggiorna anche il seed mostrato. Un originale importato o un vecchio file senza valore effettivo indica **Seed non registrato**.
