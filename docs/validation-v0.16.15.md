# Verifica 0.16.15

- Vision CPU/GPU selezionabile dalla chat e persistente dopo ricaricamento. CPU resta il default; provider API gestisce Vision sul server. GPU richiede il backend LLM CUDA o Vulkan. Il cambio vale dal prossimo messaggio e dalla rigenerazione, mantenendo il numero di layer LLM scelto.
- Test di avvio verificano i flag distinti del proiettore, il riavvio quando cambia dispositivo, il riuso senza variazioni, validazione e stima RAM/VRAM comprensiva del proiettore.
- Descrizioni preliminari delle figure slide: Thinking Off, massimo 1.792 token per gruppo di quattro immagini, 100 parole richieste per immagine e schema con massimo 1.200 caratteri per descrizione. Il limite della risposta finale resta invariato. Descrizioni incomplete segnalate, immagini conservate senza attribuzione di contenuti non analizzati. Cancellazione propagata.
- Test browser con Edge su dati sintetici: salvataggio CPU/GPU tramite API reale, persistenza dopo ricaricamento, badge coerente, Vision Off e layout mobile senza scorrimento orizzontale.
- Suite Python completa e suite JavaScript eseguite con il runtime privato. Registri locali in work/tests-v01615-final.log; test browser in tests/browser-vision-device.mjs.
- Il motore CUDA locale riconosce --mmproj-offload e --no-mmproj-offload, verificati tramite --help. La richiesta autorizzata del proprietario ha caricato il modello Qwen e il proiettore originale con Vision GPU; nessun peso copiato o modificato. Questo non certifica ogni GPU/backend/modello.
