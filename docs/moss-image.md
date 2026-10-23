# MOSS-Image opzionale

MOSS-Image crea immagini da testo e offre **img2img sperimentale con una sola immagine di partenza**. Si seleziona nel menu dei modelli immagini della chat; non sostituisce automaticamente i modelli già scelti. Il modello SFT non è addestrato come un modello Edit: questa modalità ricodifica la foto con il VAE e parte dal suo latente, senza promettere conservazione dell'identità o modifiche semantiche precise.

Per usarlo seleziona MOSS in **Immagini**, allega una foto e scrivi il risultato desiderato. In **Impostazioni Immagini** trovi **Intensità img2img**: 0,65 iniziale, da 0,05 a 1. Valori bassi conservano maggiormente la composizione; 1 riparte dal rumore e può ridisegnare tutto. Il controllo si salva con gli altri parametri della chat e nei preset personali; Undo e Ricarica richiesta lo recuperano. Il prompt prevale, per esempio «intensità 0,35» o «denoise 0.5». Senza allegati il campionamento resta interamente da testo, indipendentemente dall'intensità salvata.

Con formato **Automatico** l'uscita segue le proporzioni dell'immagine conservando l'area richiesta; un formato o dimensioni esplicite nel prompt hanno priorità. Il riferimento viene adattato e, se necessario, ritagliato alla tela scelta prima della codifica; i soli bordi aggiunti per la griglia interna vengono rimossi all'uscita. Non viene caricato un secondo modello di editing. [Gli autori MOSS descrivono ancora il supporto reference come una funzione in esplorazione](https://huggingface.co/OpenMOSS-Team/MOSS-Image-SFT/discussions/1).

Il preset ufficiale integrato è **50 passi, CFG 3, Euler, sgm_uniform**, con shift 5 e salto del blocco 22 nel ramo negativo (Simple SLG). Nella chat scegli **Immagini → Impostazioni Immagini → MOSS**: megapixel, formato, passi, CFG, sampler, scheduler e seed sono direttamente visibili. Le scelte restano per questo modello in questa chat e vengono salvate con ogni richiesta; **Ricarica richiesta** le recupera. Non cambiano le Preferenze generali. **Annulla ultima modifica** recupera la configurazione precedente; la cronologia resta disponibile anche riaprendo la chat. **Seed -1** sceglie un valore casuale; un seed fisso permette di confrontare un parametro alla volta. **Ripristina preset del modello** torna ai valori delle Preferenze. Il componente opzionale Turbo DMD2 è disponibile nelle impostazioni del modello, quando installato.

Per cambiare invece il preset generale: **Preferenze → Impostazioni immagini → Configurazione del modello → MOSS → Avanzate**. Il preset standard resta disponibile con **Ripristina predefiniti**.

Nella stessa modale della chat, la tendina **Preset MOSS** contiene **Ufficiale** (Euler / sgm_uniform, 50 passi, CFG 3) e **Fizgig** (res_multistep / simple, 30 passi, CFG 4, sperimentale). Queste due ricette impostano il campionamento e il negativo generale dell’app modificabile, conservando megapixel, formato e seed attuali; shift 5 e Simple SLG al blocco 22 restano quelli del motore MOSS. Non attivano alcuna generazione.

Per conservare una configurazione completa imposta i parametri, scrivi un **Nome del preset** e premi **Salva preset**. Vengono salvati anche megapixel, formato, seed e prompt negativo. I preset personali restano nelle impostazioni dell'app e sono richiamabili dalle altre chat dello stesso spazio di lavoro, anche dopo un riavvio. Salvare con lo stesso nome aggiorna quel preset; i due inclusi non vengono sovrascritti. **Elimina preset** rimuove solo il preset personale selezionato, senza modificare i valori correnti. La selezione di un preset può essere annullata con **Annulla ultima modifica**. Il prompt ha sempre priorità sui parametri del preset.

Puoi scrivere descrizioni normali anche con Assistant Off: il testo originale arriva direttamente a MOSS e non servono tag. Assistant On usa il modello chat per riformulare la descrizione.

Con **Assistant On** le richieste spaziali (per esempio «un gatto a sinistra, una pianta a destra, titolo “Ciao!” in alto») vengono ora tradotte nel **layout JSON ufficiale MOSS**. L’Assistant pianifica oggetti, testi e riquadri; l’app converte le coordinate nel sistema pixel centrato usando le dimensioni della modale o del prompt, che conserva la priorità. Il passaggio compare come **Assistant · MOSS · traduzione delle posizioni**. La conversione mantiene il centro anche per immagini generate su una griglia leggermente più grande e ritagliate senza ridimensionamento. Se il layout è invalido il lavoro si ferma prima di generare, senza correggere silenziosamente coordinate invertite.

Un layout JSON ufficiale già scritto viene conservato senza farlo riscrivere all’Assistant. Con **Assistant Off** il testo resta invariato: puoi usare descrizioni normali o incollare direttamente un layout valido. Non servono tag speciali. Le posizioni guidano il modello ma non garantiscono una disposizione esatta al pixel. La conversione e il passaggio nella pipeline sono verificati con test; non è ancora stato fatto un confronto GPU delle immagini generate con questa nuova traduzione.

Accanto al seed, **Usa ultimo seed** recupera il valore effettivo dell’ultima immagine completata con il modello selezionato nello stesso spazio di lavoro, anche da un’altra chat o dopo un riavvio. Recupera anche i seed generati quando avevi scelto `-1`, senza usare il valore casuale ancora non risolto della richiesta. Non modifica gli altri parametri e non avvia generazioni; puoi annullarlo con Undo. Se non esiste un risultato utilizzabile, lascia il campo invariato e lo segnala. Per tornare alle varianti casuali reimposta `-1`. Un seed esplicito nel prompt conserva la priorità.

Anche passi, CFG, sampler, scheduler e seed possono essere specificati nel prompt e prevalgono sui valori della modale. Esempio: «Un faro, 1024x576, 30 passi, CFG 3, sampler euler, scheduler sgm_uniform, seed 42». I parametri salvati restano disponibili per il lancio successivo.

Nella modale imposta **megapixel + formato**. I megapixel sono milioni di pixel: **2,25 MP + 1:1 = 1500×1500**; **2,25 MP + 16:9 = 2000×1125**. L'uscita non viene ridotta per farla entrare nella vecchia griglia di 64 pixel. Il pannello mostra le dimensioni effettive previste; alcuni motori possono arrotondare leggermente verso l'alto sulla propria griglia.

Il prompt ha priorità. Sono riconosciuti **1500*1500**, **1500x1500**, **2,25 MP**, **16:9**, passi, CFG, sampler, scheduler e seed. Dimensioni esatte prevalgono su megapixel e formato. MOSS usa una griglia interna di 16 pixel: per un'uscita 1500×1500 genera 1504×1504 e ritaglia i soli bordi, senza ridimensionare o ricampionare i pixel. Il limite esposto è 4 MP. Il precedente test 16:9 da 44 secondi era a 1024×576; non misura le prestazioni a 2,25 MP.

Il preset ufficiale resta Euler / sgm_uniform, 50 passi e CFG 3. Una [prova originale dello sviluppatore di Fizgig](https://www.reddit.com/r/StableDiffusion/comments/1x8qh5c/mossimage_comes_to_fizgig/) propone res_multistep / simple, 30 passi e CFG 4. Questa è un'alternativa sperimentale da confrontare a pari risoluzione e seed, non un miglioramento garantito. res_multistep è disponibile nel menu. Per SFT il prompt negativo ufficiale è vuoto. Su richiesta dell’utente, l’app propone invece un negativo generale leggero: `low quality, blurry, jpeg artifacts, bad anatomy, malformed hands, extra fingers, missing fingers, extra limbs, distorted face`. Non contiene restrizioni su soggetti, abiti o contenuti. È già visibile e modificabile nella modale immagini della chat e nelle Preferenze avanzate; si può anche svuotare completamente. Le personalizzazioni non vuote restano valide. Le vecchie caselle vuote della chat adottano il nuovo default una sola volta; svuotarlo in seguito resta una scelta salvata. Questo negativo è una personalizzazione dell’app, non parte della ricetta ufficiale upstream. Le indicazioni della guida Base non vanno confuse con un obbligo per SFT.

## Collegamento e spazio

Puoi centralizzare i modelli immagine in una cartella a tua scelta, anche condivisa con Forge. I diffusori, incluso MOSS e Qwen Image Turbo, possono stare in **Stable-diffusion**; gli encoder in **text_encoders** e i VAE in **vae**, mantenendo le sottocartelle originali del download. I collegamenti nell'app conservano ID e impostazioni quando vengono aggiornati ai file effettivi. Non occorre tenere una seconda copia in Downloads; l'app non presume un disco o una cartella Forge specifici.

I componenti aggiuntivi ufficiali sono Qwen3.5-9B W4A8 GPTQ (7,34 GB) e il VAE FLUX.2 (0,34 GB), oltre al diffusore INT8 da 5,41 GB. Verifica i percorsi e lo spazio sulla tua installazione: questi pesi opzionali non vengono inclusi nel pacchetto dell'app.

L'INT8 pruned usa proiezioni QKV unite. L'adattatore le separa mantenendo intatti valori quantizzati e scale per riga, poi richiede il caricamento completo dei pesi: parti mancanti bloccano la generazione invece di produrre un'immagine con pesi non inizializzati. Il core condiviso non viene modificato.

Per un'altra installazione: `scripts/install-moss.py --model-root PERCORSO_ASSOLUTO`. Il programma scarica solo encoder e VAE, controlla SHA256 e installa il piccolo adattatore ufficiale a revisione fissata. Non aggiorna il runtime video o il core condiviso. Collega poi diffusore, encoder e VAE dal profilo **MOSS-Image** nei modelli locali.

Per scaricare esplicitamente il diffusore SFT BF16 verificato nella stessa root, da PowerShell:

```powershell
.\runtime\python\python.exe -X utf8 .\scripts\download-moss-bf16.py --model-root "$env:USERPROFILE\H3-Models"
```

Sostituisci la cartella d'esempio con la tua. In alternativa `--output PERCORSO_ASSOLUTO_FILE`
sceglie il singolo file; `--verify-only` controlla un file esistente senza download
o scritture. Revisione, dimensione e SHA256 sono fissati; la verifica non carica
modelli o librerie GPU e non collega automaticamente il peso nell'app.
Non dipende da file di lavoro di altre installazioni. Richiede circa 10,16 GB
per il diffusore e 8 GiB di margine; poi collega i tre componenti nelle impostazioni.

## Precisione e memoria

Puoi collegare una variante completa FP16/BF16 dello stesso diffusore con lo stesso profilo. Il file da circa 9–10 GB non rappresenta il fabbisogno totale: servono anche encoder, VAE, attivazioni e RAM per le parti scaricate dalla GPU. Sulla RTX 5070 Ti da 16 GB è una possibilità da misurare con offload e una risoluzione prudente; non è garantito che ogni formato o risoluzione entri in memoria. Il runtime seleziona la precisione d'inferenza supportata dal modello. L’INT8 resta disponibile. MOSS SFT BF16 è opzionale: scaricalo e collegalo esplicitamente se vuoi provarlo; il pacchetto dell'app non contiene il diffusore. Il file verificato occupa 10,16 GB e riusa encoder GPTQ e VAE compatibili già collegati. Il 19 ottobre 2026 è riuscita sul PC di riferimento una prova GPU image-to-image a 512×512, 10 passi, Euler / sgm_uniform, CFG 3, seed 42 e intensità 0,35: immagine valida e riferimento inoltrato. Questa prova di funzionamento non dimostra un vantaggio qualitativo rispetto a INT8 e non misura il limite alle risoluzioni maggiori o la disponibilità del modello su un altro PC.

Fonti: [MOSS-Image ufficiale e preset ComfyUI](https://github.com/OpenMOSS/MOSS-Image/blob/main/comfyui/README.md), [componenti ufficiali Comfy-Org](https://huggingface.co/Comfy-Org/MOSS-Image).


## Turbo DMD2 e Kromoss

In **Immagini → Impostazioni Immagini**, seleziona MOSS INT8, MOSS BF16 o Kromoss,
poi attiva **Turbo DMD2 · 8 passi**. La stessa scelta è nelle Preferenze immagini
per modello. Il flag imposta 8 passi, CFG 1, Euler / SGM Uniform; il motore mantiene
shift 5 e non applica il salto SLG del ramo negativo. A CFG 1 il negativo salvato
non viene valutato. Formato, megapixel, seed e intensità img2img restano indipendenti.
I parametri tecnici del Turbo sono disabilitati nella modale durante l'attivazione;
le richieste esplicite nel prompt hanno ancora priorità. Disattivando il flag si
ripristinano passi, CFG, sampler e scheduler precedenti, anche dopo chiusura e
riapertura della chat. La ricetta nel PNG/JSON include flag e valori di ripristino.
I preset inclusi Ufficiale/Fizgig tornano alla generazione normale; un preset
personale può conservare anche il Turbo.

Il file è `lodestones/Kromoss/8-steps-dmd2-lora.safetensors`, revisione
`7f9bb7b06d7b6c27d294b0bab5a2b3056c379279`, SHA256
`7683fe1fb51f73f5d690f24dd6b7f46f31ab9a9873729a854ac5c9a420ffe6f2`.
Occupa 1,19 GB ed è conservato separatamente in Forge `models/Lora/MOSS`.
L'adattatore applica 252 proiezioni come residui FP32, senza fondere i delta nei
pesi BF16/INT8. I collegamenti vengono rimossi anche su errore; disattivare Turbo
non lascia patch nella generazione successiva. Il percorso installato viene letto
da `data/moss-dmd2.json`, non da testo arbitrario del prompt.

**Kromoss INT8** è un collegamento separato allo stesso profilo MOSS, con gli encoder
e VAE già presenti. I pesi del diffusore occupano 5,41 GB. I modelli MOSS SFT
restano disponibili. L'autore documenta DMD2 su MOSS Base/Kromoss: il trasferimento
allo SFT è sperimentale e richiede valutazione visiva; la compatibilità dei tensori
non prova che tutti i prompt o img2img migliorino. Né i 4 passi né una risoluzione
più bassa vengono imposti silenziosamente. Non confondere questo LoRA immagini
con DMD/PDD/Turbo per MiniMax H3 video.

Fonte: https://huggingface.co/lodestones/Kromoss . Installazione e prove locali:
`work/moss-dmd2-2026-10-23`. Distinguere test isolati, browser e prove GPU reali nei
relativi risultati salvati; il numero di passi non misura da solo il tempo totale.
