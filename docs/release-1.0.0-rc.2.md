# H3-Chat 1.0.0-rc.2

Seconda candidata alla 1.0.0. Include le funzioni della [prima candidata](release-1.0.0-rc.1.md)
e la riorganizzazione del primo avvio, delle installazioni e delle impostazioni.
La versione stabile resta 0.19.2. I pesi generativi non sono inclusi nei pacchetti.

## Novità rispetto alla rc.1

- Primo avvio guidato: utilizzo locale, API o misto; rilevamento hardware,
  suggerimento da applicare esplicitamente, selezione dei modelli e memoria.
- Centro **Modelli e installazioni** anche nella barra laterale: catalogo,
  collegamenti locali, componenti software, modelli RAG/trascrizione e download.
- Ricerca e filtro del catalogo, dimensioni dei download e verifica preventiva
  della compatibilità stimata con i parametri attuali, senza cambiare i default.
- Preferenze divise per argomento con sottosezioni, aiuti espandibili e
  conservazione dei valori non ancora salvati mentre si cambia pagina.
- Impostazioni Slide, Locandine, Infografiche, Agente e Crea sfondi più compatte;
  comandi principali e preset raggiungibili, adattamento agli schermi piccoli.
- Heabsy tra i preset dei provider Chat Completions, con indirizzo precompilato.
  La chiave si inserisce soltanto nel campo protetto. Nessun account viene
  configurato e nessuna richiesta autenticata viene inviata automaticamente.

## Verifiche e limiti

I pacchetti hanno checksum e rapporti per Windows x64, macOS Apple Silicon e
Linux x64; il percorso Linux comprende anche il collaudo Kali. I controlli UI
usano dati temporanei, provider simulati e download intercettati. Non caricano
pesi reali e non certificano ogni combinazione di modello, GPU o provider.

Le dimensioni mostrate per i componenti sono quelle del download; l'estrazione
può richiedere spazio aggiuntivo. Le stime RAM/VRAM non sono una garanzia.
Su Mac i componenti nativi compatibili si aggiornano con il pacchetto dell'app;
i runtime Windows/CUDA non si installano da quel catalogo.

Seguire la [checklist di collaudo e aggiornamento](release-candidate-testing.md).
Prima di aggiornare fermare i lavori e conservare una copia distinta di `data`,
modelli, runtime e percorsi esterni. Le chiavi protette possono richiedere un
nuovo inserimento passando a un altro PC o sistema operativo.

Brochure multipagina e animazioni native PowerPoint restano nel
[piano successivo alla 1.0](post-1.0-roadmap.md). Il nuovo multiagente rimane escluso.
