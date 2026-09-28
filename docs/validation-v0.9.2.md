# Verifiche H3-Chat 0.9.2

Ambiente: Windows x64, Python embedded 3.13.15, RTX 5070 Ti 16 GB. Verifiche del 28 settembre 2026.

- 109 test Python e 2 test JavaScript: collocazione GPU indipendente da Residenti/A richiesta, stima OOM, separazione passi/blocchi VAE, bundle corrotto/non allineato, ripetibilità installazione e conservazione dati, oltre alle regressioni precedenti.
- Clone simulato copiando solo file versionati e nuovi file da pubblicare in una cartella con spazi e accenti. Installazione completa con PATH limitato a Windows/System32, senza Python di sistema, Node.js o compilatori: Python privato, interfaccia, launcher, motori CPU chat/immagini/musica scaricati e verificati. DLL immagini e protocollo musica verificati.
- Chat reale su CPU nel clone con Qwen3 0.6B Q4 collegato esternamente: risposta corretta a 17 × 19. Avvio del launcher con console log, API stato, asset dell'interfaccia e arresto verificati; installazione rifiutata mentre quella copia è in esecuzione. Seconda installazione senza download e database byte per byte invariato.
- Pikon Realism v2 SDXL, VAE incluso nel checkpoint: CUDA, 768×768, 13 step, LCM/simple, CFG 1, seed 123456, A richiesta, Assistant Off. Due PNG validi e ispezione visiva riuscita. Prima richiesta 132,83 s: caricamento 128,23 s, generazione e salvataggio 4,60 s. Richiesta successiva sullo stesso processo: 3,78 s, di cui circa 0,97 s per il VAE. Nessun secondo passaggio di diffusione: 13 step seguiti da 25 blocchi VAE, esplicitamente distinti nell'attesa. Hires disattivato.
- Il registro nativo attribuisce circa 125,77 s del primo caricamento alla lettura dei pesi dal disco SATA. Il test avveniva durante la prova di installazione: non è una misura isolata delle prestazioni del disco. Nessuna promessa di caricamento immediato a freddo o accelerazione costante della cache.

Le prove di inferenza nuove coprono Pikon su CUDA e la chat CPU. Vulkan, Ming/Qwen 2.1 nella nuova collocazione interamente GPU e tutte le altre combinazioni di modello/hardware non sono stati collaudati nuovamente in questa versione. La scelta GPU richiede VRAM sufficiente; non viene effettuato un ripiego silenzioso del calcolo immagini sulla CPU. Il mmproj della chat resta CPU. I test precedenti verificano che A richiesta scarichi il modello precedente e che il mmproj resti CPU anche in Residenti.

Dati, pesi e registri di collaudo non fanno parte del repository né del pacchetto.
