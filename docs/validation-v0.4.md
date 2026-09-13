# Verifica H3-Chat 0.4.0

- 35 test Python con il runtime embedded Windows: percorsi assoluti esterni, GGUF suddivisi, mmproj automatico/manuale/disattivato, componenti immagini in directory diverse, file mancanti e ripristino dei collegamenti, persistenza, controllo formato, protezioni HTTP e regressioni di chat/canvas/Think/memoria.
- 2 test JavaScript del rendering numerico.
- Edge desktop e mobile: scelta tramite Sfoglia, percorsi con spazi e caratteri accentati, collegamento LLM vision e FLUX con componenti separati, selezione nei menu del Setup, persistenza dopo ricaricamento, modifica e scollegamento. I file originali sono rimasti presenti dopo Scollega.
- Prova reale con una copia pulita dello ZIP: SmolVLM 500M e il suo mmproj sono stati caricati dalla cartella originale, esterna alla copia dell'app. Il mmproj è stato trovato automaticamente. La richiesta vision su un'immagine rossa ha restituito «Red.». Nessun GGUF è stato copiato nella cartella della nuova installazione; gli hash dei pesi originali sono rimasti identici.

La prova reale usa CPU. L'inferenza immagini su CPU resta coperta dal collaudo 0.3; in questa versione vengono verificati l'associazione e il passaggio dei percorsi assoluti dei componenti. CUDA/Vulkan e ogni possibile architettura/checkpoint esterno non sono certificati da questo collaudo. File e percorsi delle prove non sono inclusi nella release.
