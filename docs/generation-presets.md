# Preset delle richieste

Sotto una risposta, **Salva preset** conserva con un nome i parametri della
richiesta originale. Il comando è disponibile anche per lavori interrotti o
falliti, se la ricetta è presente. **Preset richieste**, nel compositore e nelle
finestre delle impostazioni, apre il selettore con filtro per modalità.

Sono supportati chat, immagini, video, musica, Voice, trascrizione, slide,
locandine, infografiche, Studio, Manim, calcolo e lotti. Il richiamo non invia
nulla: applica il modello, il suo tuning e i controlli alla bozza. Il prompt
mantiene la priorità. I predefiniti globali restano invariati. I preset MOSS
e i preset del solo pannello Slide/Sfondi già disponibili restano utilizzabili.

Prompt, allegati, testo fonte dello Studio, testi delle canzoni, sorgenti di
codice, fonti RAG selezionate, chiavi API e autorizzazioni dell’Agente non vengono
inclusi. Se un preset richiede un audio o un'immagine, allegare la nuova fonte.
I collegamenti a modelli o raccolte non più disponibili devono essere sostituiti;
nessun download viene avviato dal caricamento del preset.

Per immagini con dati di creazione registrati vengono salvati i parametri
effettivi, compreso il seed. Per le altre modalità si conserva la politica di
seed della richiesta. Gli script/video già creati non sono incorporati nel
preset. Un preset tratto da Modifica video prepara i parametri per una nuova
richiesta video; non copia intervalli, patch o filmato sorgente.

La raccolta è nel workspace dell’account corrente (`generation-presets.json`),
con al massimo 50 preset per modalità. Salvare lo stesso nome nella stessa
modalità aggiorna il preset; eliminarlo non cancella risultati o file generati.

# Riutilizzare illustrazioni delle slide

**Ricarica richiesta** recupera anche il catalogo delle illustrazioni generate
da quel lavoro, comprese quelle già terminate prima di un'interruzione. In
Impostazioni Slide compare **Riusa immagini già create**, inizialmente attivo.
Richiede Illustrazioni AI attive. Se disattivato si torna alla normale nuova
generazione del piano immagini.

Il pianificatore riceve descrizione, proporzioni e dimensioni delle immagini
disponibili. Può riassegnarle a slide differenti e richiederne di nuove quando
cambiano soggetto, stile o composizione. Solo gli ID del catalogo autorizzato
sono accettati. File mancanti vengono esclusi, senza leggere immagini da altre
chat. Le nuove figure si aggiungono al catalogo riutilizzabile (ultime 100).

Il numero di figure riusate e nuove è registrato nei metadati del lavoro. Se
tutte le figure pianificate vengono riusate il motore immagini non viene
caricato. La scelta dipende dal piano LLM: non è una garanzia di equivalenza
semantica o di identico layout tra due richieste.
