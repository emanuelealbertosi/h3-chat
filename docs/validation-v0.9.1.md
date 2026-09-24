# Verifiche H3-Chat 0.9.1

Errore riprodotto aprendo le impostazioni con i file UI aggiornati e un motore 0.8.0 rimasto attivo su una seconda porta: mancava `llm_options` nella risposta di stato.

- 102 test Python superati, inclusi rilevamento delle istanze della stessa installazione, riavvio di versioni precedenti inattive, conservazione di generazioni/download attivi, arresto di tutte le istanze e intestazioni anti-cache dell’interfaccia.
- Regressione Edge: stato del vecchio motore spiegato senza errore JavaScript; apertura delle impostazioni dopo aggiornamento dello stato, sulla stessa pagina e senza modificare i valori salvati.
- Verifica locale del percorso reale di aggiornamento: motore riavviato sulla stessa porta, impostazioni e chat confrontate prima/dopo, console dei log ancora aperta.
- Ricerca delle porte eseguita in parallelo, con timeout limitato, per evitare un’attesa cumulativa all’avvio.
