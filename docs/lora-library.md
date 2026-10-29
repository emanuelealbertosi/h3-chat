# Librerie LoRA locali

In **Preferenze → Cartelle LoRA** si possono collegare fino a 20 cartelle su unità diverse. La ricerca comprende le sottocartelle, senza copiare i pesi. I collegamenti a una stessa cartella fisica vengono deduplicati.

In chat, **LoRA → Modello destinatario** mostra solo gli adattatori della famiglia del modello scelto. Krea 2 e Anima hanno elenchi distinti; anche FLUX.1 Krea appartiene a una famiglia diversa da Krea 2. La modale di modifica video usa lo stesso indice, limitato agli adattatori MiniMax H3.

Per i checkpoint collegati con il profilo generico Stable Diffusion, l'header distingue SD 1.5, SD 2 e SDXL: il selettore non mescola queste tre famiglie. Se non riesce a identificarlo, non propone abbinamenti generici.

L'indice legge esclusivamente gli header dei safetensors. Accetta coppie LoRA standard, LoKr completi e LoHa completi. Usa prima i metadati del modello base; quando mancano, riconosce le architetture note dalle dimensioni e dai nomi delle coppie di tensori. Il nome del file da solo non basta. I file non riconosciuti restano esclusi dalle selezioni; VAE, patch di differenze e file incompleti non vengono presentati come LoRA.

Anche MOSS senza metadati viene riconosciuto quando attenzione e FFN gated hanno
insieme nomi e dimensioni coerenti. La sola larghezza 3072 o il nome del file non
bastano: non viene confuso con FLUX.1 o Qwen Image.

**Aggiorna elenco** rileva i file aggiunti o spostati. Nessun adattatore viene selezionato automaticamente. Il caricamento verifica anche la compatibilità dei pesi con il checkpoint effettivo; appartenere alla stessa famiglia non garantisce la qualità del risultato o il supporto di ogni variante di adattatore.
