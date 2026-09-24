# Verifiche H3-Chat 0.9.0

- 96 test Python superati: preset LLM indipendenti, migrazione dei valori esistenti, snapshot dei lavori, contesto 64k, stime della memoria, contratto Assistant per modello, inoltro dei tag ai motori nativi, Assistant Off senza LLM, condizione negativa Qwen a CFG 1 e regressioni dei motori esistenti.
- 2 test del renderer superati.
- Browser Edge: preset LLM A/B senza cambiare il modello predefinito; ripristino alla selezione; preset immagini distinti; indicazione tag inglesi per Anima/SDXL e prosa per Ming/Qwen.
- Browser Edge: salvataggio e riapertura di 64k/128k/256k, contesto dichiarato nel GGUF, avviso oltre il contesto dichiarato e modello con metadati mancanti.
- Browser Edge: attesa creazione/modifica immagini, musica e canvas; fase aggiornata, passi, tempo trascorso e rimozione dell'indicatore alla fine. Queste prove usano lavori simulati senza generare media.
- Browser Edge: regressione errori nella modale, valori conservati, retry, schermo piccolo e messaggi lunghi.
- Aggiornamento locale: confronto delle impostazioni prima/dopo; i valori esistenti sono conservati e registrati nel preset dell'LLM attuale.

Le prove dei contratti dei motori usano inferenza simulata; non misurano la qualità dei tag prodotti da ogni LLM. Non è stato eseguito un nuovo benchmark GPU né una generazione completa a 64k: memoria, qualità e tempi effettivi dipendono dal modello e dal computer. A CFG 1 l'ottimizzazione Qwen elimina il secondo passaggio dell'encoder; non elimina il caricamento dei pesi e i trasferimenti alla GPU.
