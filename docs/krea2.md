# Krea 2 e LoRA locali

In **Setup → Motori immagini standalone → Krea 2**, collega tre file già presenti sul computer:

- Diffusore Krea 2, per esempio RedCraft KREA2 RedMix.
- Encoder `qwen3vl_4b_fp8_scaled.safetensors`.
- VAE `qwen_image_vae.safetensors`.

I percorsi possono appartenere a cartelle e unità diverse: i file non vengono copiati. Il profilo usa il motore standalone incluso in H3-Chat; non richiede Forge o un server ComfyUI.

Il preset iniziale è **1024 × 1024, 8 passi, CFG 1, Euler / Simple**, modificabile per modello in **Parametri di generazione**. La selezione in chat utilizza il preset del modello scelto. Collegare il modello non cambia il predefinito di creazione o modifica.

Questo profilo genera immagini **da testo**. Krea 2 non viene presentato come un modello Edit: il supporto a riferimenti di stile richiede un adattatore e un percorso di condizionamento dedicati. FLUX.1 Krea è una famiglia diversa.

In **Preferenze → Cartelle LoRA**, collega la cartella degli adattatori. In chat premi **LoRA**, scegli Krea 2 come destinatario e seleziona i file compatibili, impostando il peso. I LoRA standard e LoKr Krea 2 vengono riconosciuti dai metadati e, per i LoRA Turbo senza metadati, dalla struttura dei tensori. Gli adattatori di altre famiglie vengono segnalati come incompatibili.

Nessun LoRA viene applicato automaticamente, incluso Turbo: un diffusore già distillato potrebbe non averne bisogno. Un file patch contenente soltanto differenze di pesi non viene elencato come LoRA.

Riferimenti del profilo: [documentazione ComfyUI Krea 2](https://github.com/Comfy-Org/docs/blob/main/tutorials/image/krea/krea-2.mdx) e [modelli Krea 2](https://huggingface.co/Comfy-Org/Krea-2).


Verifica reale del 15 ottobre 2026: RedCraft KREA2 RedMix, 1024×1024, 8 passi, CFG 1, Euler/Simple, Realistic Slider Rank1 a 0,4: immagine generata e decodificata. Circa 108 secondi complessivi da freddo sul PC di sviluppo; non è una misura dei soli passi. Il runtime evita i tensori di inferenza nelle fasi che devono ripristinare pesi quantizzati dopo un LoRA. Il selettore nasconde i LoRA delle famiglie incompatibili.
