# Verifica 0.14.1

- Suite Python: 238 test; rendering JavaScript: 2 test.
- Cronologia: recupero degli artefatti già presenti nei messaggi e del vecchio canvas; aggiornamenti in streaming senza una voce per ogni frammento; risultati precedenti conservati dopo rigenerazione; copie manuali separate dall’originale.
- API: selezione e ripristino limitati alla chat corretta, media delle vecchie versioni ancora utilizzabili, salvataggi/ripristini bloccati durante la scrittura del motore, cancellazione della cronologia insieme alla chat.
- Browser Edge, dati sintetici e archivio temporaneo: frecce, elenco, immagini, formule e codice; selezione stabile durante un nuovo lavoro; export Markdown; ripristino per le richieste successive; modifica, ricaricamento, isolamento tra chat e layout mobile a 390 px. Nessun errore JavaScript.
- Renderer Manim reale: scena 3D, camera, animazione, testo, immagine e formula MathTex; durata verificata, lettura/scrittura fuori dal lavoro e rete negate. Interruzione verificata anche sui processi figli, con rimozione della cartella temporanea e della lettera di unità.
- Compatibilità AppContainer: i processi che chiedono una destinazione nulla scrivono in un file temporaneo della propria cartella; non servono permessi aggiuntivi sul dispositivo Windows NUL.

La prova della cronologia usa esclusivamente fixture sintetiche e non richiede di caricare modelli o aprire conversazioni dell’utente. Si ripete con `node tests/browser-canvas-history.mjs` e Playwright/Edge disponibili; il server temporaneo si arresta alla fine.
