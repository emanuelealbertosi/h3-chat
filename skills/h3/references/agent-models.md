# Agent: modelli, LoRA e download

list_model_catalog fornisce ID reali, modelli pronti e componenti verificati.
download_catalog_model avvia il gestore H3; model_download_status ne verifica la
conclusione. Non dichiarare pronto un download appena avviato. Un'architettura
nuova richiede un motore: scaricarla non basta.

Leggi la pagina con read_web_page se serve ricavare il link diretto. Poi usa
download_web_file: scarica negli output H3, senza eseguire o estrarre. Riporta nome,
dimensione e SHA256. Un hash calcolato identifica i byte, non certifica l'autore;
un hash atteso confrontato è un controllo aggiuntivo. Non aggirare accessi protetti.

install_lora_from_url scarica soltanto .safetensors e controlla struttura e famiglia
rispetto al model_id H3. folder_number sceglie una cartella LoRA già configurata,
da 1; senza libreria configurata registra models/loras/Agent. Non sovrascrive file.
Verifica installed e available_in_lora_library: disponibile non significa già
applicato alla generazione. Se incompatibile il file rimane soltanto negli output.

set_model_preset salva impostazioni validate senza inferenza; non cambia il default
salvo make_default=true richiesto dall'utente. Per MOSS INT8, BF16 e Kromoss,
moss_turbo=true applica DMD2: 8 passi, CFG 1, Euler, sgm_uniform.
create_image_lot espone la stessa opzione: non basta citarla nel prompt visivo.
Se DMD2 manca o il modello non è MOSS, riferisci l'errore; niente sostituzioni
silenziose. Riporta i parametri restituiti senza inventare qualità o velocità.
