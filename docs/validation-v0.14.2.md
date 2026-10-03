# Verifica 0.14.2

Suite completa: 240 test Python e 2 test JavaScript superati.

- Identità LLM letta dai file già configurati: nome GGUF effettivo, percorso assoluto, nome salvato e nome interno separati.
- Due file con lo stesso nome interno generico rimangono distinguibili; un’etichetta personale viene mantenuta insieme al file. Un percorso mancante resta visibile come file previsto.
- I nuovi collegamenti suggeriscono il nome del file invece del nome interno del GGUF. Identificatori dei modelli, preset e percorsi configurati restano invariati.
- Verifica browser con modelli GGUF sintetici: dettagli cliccabili in chat, scelta nel Setup, percorso visibile, cambio tra due modelli, impostazioni per modello e layout mobile.
- La prova completa della cronologia del canvas continua a passare insieme alla verifica dei nomi.
- I nomi del file vengono usati anche nell’attesa del caricamento, nei log e nella lista dei modelli in memoria.
