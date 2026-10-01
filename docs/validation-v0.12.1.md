# Verifiche H3-Chat 0.12.1

Windows x64, Python privato 3.13. Dati e chiavi di collaudo isolati in cartelle
temporanee; nessuna modifica alle chat o ai modelli scelti dall’utente.

- **165 test Python, 2 JavaScript**. 24 nuove prove dei provider API:
  persistenza e roundtrip DPAPI, anche concorrenti, assenza di chiavi in stato UI/messaggi/job,
  modifica e rimozione, indirizzi, cambio endpoint, elenco modelli e probe,
  blocco modifiche durante i job, chat/router/SSE, canvas JSON, Vision On/Off,
  Assistant SDXL a tag inglesi, musica e video, livelli thinking, formati JSON,
  HTTP 401, redirect rifiutati, stream incompleti e con errori, annullamento
  durante uno stream fermo, Residenti senza precaricamento API, memoria LLM zero.
  Il server HTTP di fixture risponde su loopback; non è un provider cloud.
- **LLM reale su endpoint compatibile**: Qwen3 0.6B Q4 con llama-server CPU
  esposto temporaneamente come endpoint API. H3-Chat ha completato una richiesta
  fino alla risposta “7 + 5 = 12” tramite il nuovo percorso API. Nessun processo
  LLM nell’Engine configurato API; il processo del server di collaudo è stato
  chiuso dopo la prova. Non certifica qualità o prestazioni dei servizi cloud.
- **Chrome headless**: inserimento provider personalizzato, caricamento elenco,
  probe, salvataggio, campo chiave svuotato, Usa in chat, modifica con chiave
  non esposta, risposta in chat, badge Vision/API, GPU e MTP disabilitati.
  Nessun errore JavaScript. Le schermate sono state controllate visivamente.
- **Pacchetto portabile da cartella nuova**: SHA-256 di tutti i 920 file,
  worker e stato della versione 0.12.1, componenti PDF/Word e lettura reale,
  salvataggio/lettura di una chiave DPAPI nell’app estratta. Nessuna chiave,
  chat, configurazione personale o peso modello nel pacchetto.

La compatibilità DeepSeek/OpenRouter e i parametri thinking/JSON sono implementati
secondo le fonti ufficiali elencate nella [guida API](api-providers.md). Non sono
state fatte inferenze autenticate su servizi cloud: non era disponibile una chiave
di collaudo e non è stato consumato credito dell’utente. Errori o differenze del
modello scelto vanno verificati con Prova connessione e modello.

Le prove PDF/Word, Whisper e media della versione precedente restano descritte
in [verifiche 0.11.0](validation-v0.11.0.md) e coperte dai test di regressione.
