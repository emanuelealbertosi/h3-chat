# LoRA MiniMax H3 per modificare video

Il pulsante **LoRA** della chat accetta anche modelli video MiniMax H3. Le cartelle collegate nelle Preferenze vengono lette senza copiare i pesi. In **Modifica clip** e **Ricrea video**, il pannello **LoRA video · modifica mirata** permette di selezionare adapter e peso oppure scegliere un safetensors dal filesystem. Le selezioni della chat per il modello originale vengono proposte anche in Modifica clip. I preset amministrativi restano invariati.

Adapter iniziali, disponibili dal [repository dell'autore](https://huggingface.co/Alissonerdx/Minimax-H3-ComfyUI):

- `minimax_h3_character_swap_v1.0_ref2va_r64_gl.safetensors`: sostituzione personaggio, almeno un'immagine di riferimento per ogni clip, prefisso `body_swap:`.
- `minimax_h3_vfx_edit_v1.0_r128_ffp.safetensors`: modifica attributi, prefisso `vfx_edit:`. Può utilizzare il primo fotogramma già modificato tramite il canale delle immagini native. È combinabile con l'automodificatore dei fotogrammi guida.

Il prefisso viene applicato automaticamente dopo l'Assistant. Per questi adapter il video sorgente viene passato come guida latente allineata a fotogramma zero, equivalente a `MiniMaxH3AddGuide`, invece del riferimento video separato. Le immagini selezionate passano dal canale delle immagini native. Intervallo, campionamento a 24 fps, proporzioni, audio originale e montaggio opzionale restano quelli richiesti.

La guida allineata occupa lo stesso canvas spaziale e temporale dell'uscita; il controllo della risoluzione separata del riferimento leggero non ne riduce la dimensione. Aumentano memoria e lavoro di codifica/attenzione: iniziare con circa 3 secondi a 0,50 MP e peso 1. Il modello originale su disco non viene modificato. I LoRA vengono fusi una sola volta per generazione sul diffusore temporaneo, un parametro alla volta, poi il diffusore viene rilasciato prima della decodifica. I tensori incompatibili fanno fallire la richiesta esplicitamente, evitando applicazioni parziali silenziose.

PDD può essere abbinato a Character Swap o VFX Edit, con il file PDD della famiglia corrispondente. I pesi di editing e PDD vengono fusi insieme una sola volta sul diffusore temporaneo; restano attive le proiezioni video/audio e le sigma addestrate di PDD. DMD, altri Turbo e LoRA non verificati sono esclusi quando PDD è attivo. La combinazione è sperimentale e va confrontata visivamente. Le richieste vengono eseguite nella normale coda condivisa.

Il [Turbo Ref2VA ufficiale a 4 passi](https://github.com/ModelTC/Minimax-H3-Turbo/blob/main/example_workflows/video_minimax_h3_ref2v_lightx2v_turbo.json), `minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors`, usa peso 1, Euler, scheduler Simple, CFG 1 e shift video/audio 12/3. Se è attivo e sono richiesti 4 passi, il lip-sync conserva questi 4 passi: il minimo di 8 passi riservato al checkpoint standard non viene applicato. Turbo e PDD sono alternative e non si sommano. Il confronto del 14 ottobre conserva tutti i risultati, ma la qualità del Turbo è stata giudicata insoddisfacente per lo scambio personaggio; i preset restano invariati.

Entrambi gli adapter sono sperimentali e addestrati principalmente su `ref2va`. Compatibilità dei tensori non significa garanzia di fedeltà dei movimenti, identità o labiale su un Hybrid, soprattutto per clip lunghe.

I pesi non sono inclusi nel pacchetto GitHub. Ogni installazione può scegliere le proprie cartelle. Conservare le [licenze dei singoli asset](https://huggingface.co/Alissonerdx/Minimax-H3-ComfyUI/blob/main/LICENSES.md); Character Swap ha condizioni specifiche e non consente di offrire il modello come API/SaaS remoto.
