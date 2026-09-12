# Verifica della versione 0.1.0

Verificata su Windows, 12–13 settembre 2026.

- 11 test Python: ciclo di vita chat/raccolte, archivio e pin, coda e annullamento, snapshot immutabili, recupero dopo riavvio, destinazione canvas, Unicode, validazione delle impostazioni, riferimenti multipli, ripresa download e SHA-256, estrazione ZIP, isolamento HTTP e sanificazione PDF.
- 2 test JavaScript: coordinate preservate, serie coerenti, valori finiti e rigetto di opzioni eseguibili nei grafici.
- Test browser desktop e mobile: risposta reale su CPU, persistenza del canvas, codice evidenziato, LaTeX, etichette Mermaid, grafico numerico, download Word/PDF/PNG, assenza di overflow orizzontale e di errori JavaScript.
- Export Word aperto e renderizzato con Microsoft Word; PDF e Word controllati visivamente. Verificate formule, dati, frecce ed etichette. Il PDF conserva testo e diagrammi vettoriali.
- Qwen3 0.6B: inferenza reale di testo e output JSON separato nel canvas, con chiusura del processo dopo la richiesta.
- SmolVLM 500M: download e collegamento vision verificati. Il modello è risultato poco affidabile con quattro riferimenti e in italiano; il catalogo limita questo modello a una sola immagine e ne indica i limiti. Per analisi di grafici il catalogo propone Qwen2.5-VL.
- Parametri e quattro riferimenti del motore FLUX verificati contro la CLI installata e con test del comando; inferenza FLUX/Stable Diffusion e backend CUDA/Vulkan non ancora collaudati su GPU.
- Audit npm di produzione: nessuna vulnerabilità segnalata al momento della verifica.
- ZIP standalone: avviata una copia estratta con il Python incluso, senza ambiente Python/Node esterno; motori CPU rilevati. Verificati gli SHA-256 di tutti i file e l'esclusione di dati personali e pesi dei modelli.

I test di inferenza delle diverse GPU e dei modelli immagini restano necessari prima di dichiarare una versione stabile per tutte le configurazioni. I profili VRAM rappresentano impostazioni iniziali, non limiti di consumo garantiti.
