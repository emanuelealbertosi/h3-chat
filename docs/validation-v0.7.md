# Verifiche H3-Chat 0.7.0

Ambiente reale: Windows, NVIDIA RTX 5070 Ti, Python incorporato 3.13,
PyTorch 2.13.0 CUDA 13.0, core ComfyUI fissato al commit indicato in vision-engine.md.

- 67 test Python: routing automatico/esplicito, preferenze per richiesta, Assistant,
  proiettore CPU anche in Residenti, riuso dei processi, limiti e ordine dei riferimenti,
  canvas, archivio chat, download verificati, LoRA e stime della memoria.
- 2 test del renderer: coordinate quantitative e convalida delle serie.
- Prova dell'interfaccia: scelta modello, Assistant e Vision, preset distinti,
  filesystem, canvas senza duplicazione nel corpo, persistenza e schermo da 430 px.
- Ming standard, 1024 x 1024, 12 passi: creazione e modifica riuscite.
- Qwen Image 2.1 standard, 1024 x 1024, 25 passi: creazione e modifica riuscite.
- Pacchetto estratto in una cartella separata: Qwen Image 2.1 con quattro riferimenti,
  512 x 512, 25 passi; esecuzione con il suo Python privato e pesi collegati esterni.
- Qwen 27B GGUF con mmproj sulla CPU: captioning corretto del diagramma di prova e
  preparazione del prompt Assistant nello stesso processo LLM, senza secondo caricamento.
- Import delle librerie native dalla cartella privata dell'app e verifica del protocollo
  del motore nativo precedente.

Le prove di generazione dei nuovi modelli sono state eseguite su CUDA. Il percorso CPU
è disponibile ma non è stato misurato con una generazione completa. Vulkan non è
supportato da questo motore opzionale. Nessuna prova certifica l'esattezza matematica
universale delle immagini; grafici quantitativi e diagrammi strutturati possono usare
il renderer Chart/Mermaid. I preset Viggle Turbo non sono inclusi.

I pacchetti pubblici escludono conversazioni, impostazioni personali e pesi.
I manifest SHA-256 accompagnano gli archivi. I test con pesi reali sono ripetibili
tramite tests/real-vision-smoke.py, fornendo esplicitamente la cartella dei modelli.
