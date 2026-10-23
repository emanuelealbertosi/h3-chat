# Immagini H3-Chat in SillyTavern

Il collegamento locale espone un sottoinsieme dell’API AUTOMATIC1111 e inoltra
le richieste al server H3 autenticato. I modelli e la GPU rimangono gestiti da
H3-Chat. Il server immagini H3 ascolta su 127.0.0.1:8790; SillyTavern si collega
all’adattatore su **http://127.0.0.1:8791**. Nessuna porta LAN viene aperta.

Avvia H3-Chat e poi `Avvia-server-immagini.bat`. Lo script riutilizza il server
già attivo, oppure lo abilita, e avvia l’adattatore senza riavviare i motori.
Le chiavi interne sono protette con DPAPI per l’utente Windows corrente.
Per associare un profilo SillyTavern, eseguire una volta:

```powershell
runtime/python/python.exe -X utf8 scripts/start-image-server.py --sillytavern "F:/sillytavern/SillyTavern/data/default-user/settings.json"
```

Il percorso viene ricordato. Vengono aggiornate solo le impostazioni del
generatore immagini; il precedente oggetto `sd` viene conservato cifrato in
`data/image-api-sillytavern-backup.json`.

In SillyTavern ricarica la pagina, apri **Estensioni → Generazione immagini**:

- Sorgente: **Stable Diffusion WebUI / AUTOMATIC1111**.
- URL: **http://127.0.0.1:8791**.
- Autenticazione: già configurata dallo script (utente `h3`).
- Modello: selezionabile tra i generatori immagini locali pronti di H3-Chat.
- Usa `/sd una piccola casa sulla montagna` per generare e mostrare un’immagine.

Il collegamento supporta una immagine per richiesta, seed, prompt negativo,
dimensioni, passi, CFG, sampler e scheduler. Il prompt arriva direttamente al
modello immagini; l’Assistant di H3 è disattivato per queste richieste.
SillyTavern può preparare il prompt dalla conversazione tramite il proprio LLM.
Il modello scelto nel client non modifica il predefinito della chat H3.

Durante un altro lavoro H3 restituisce «server occupato», senza interromperlo.
Il comando Stop del client può fermare soltanto la richiesta avviata da questo
adattatore. Gli output restano anche nella cronologia Server di H3-Chat.

High-res fix, ADetailer, ControlNet, LoRA via sintassi WebUI, img2img e moduli VAE
alternativi non sono implementati dall’adattatore. I VAE sono quelli del modello
collegato in H3. Gli errori del generatore restano visibili nei log di H3;
il log del collegamento è `data/logs/image-api-server.log`.

Sono inclusi Anima, MOSS INT8 e BF16, Qwen e Turbo, Ming, Krea e gli altri
modelli immagini locali pronti. I valori omessi dal client vengono presi dal
preset H3 di quel modello; quelli inviati da SillyTavern prevalgono. Quando
cambi famiglia controlla quindi anche passi, CFG e scheduler del client:
MOSS parte da 50 passi, CFG 3, Euler / SGM Uniform; Anima Base da 30 passi,
CFG 4 (i tuoi preset H3 possono differire). I nomi dei sampler vengono tradotti
per il motore nativo di Anima/SD o per il runtime MOSS/Qwen.

Riferimento del protocollo client:
https://github.com/SillyTavern/SillyTavern/blob/release/src/endpoints/stable-diffusion.js


## Varianti MOSS / Kromoss Turbo DMD2

Dopo l'installazione del componente, aggiorna l'elenco modelli in SillyTavern.
Per ogni MOSS/Kromoss disponibile appare anche una voce **· Turbo DMD2**.
È un alias del modello originale, non una seconda copia dei pesi: invia lo stesso
ID modello a H3 con il flag Turbo. La voce Turbo imposta automaticamente 8 passi,
CFG 1, Euler e SGM Uniform anche quando il client invia i propri valori predefiniti.
Dimensioni e seed richiesti dal client restano validi; il prompt esplicito viene
interpretato normalmente da H3. La voce senza Turbo usa il percorso normale.
Gli alias hanno ID `ID_MODELLO::dmd2` nell'adapter locale; non sono nuovi checkpoint
e non richiedono un avvio separato di ComfyUI. Su MOSS SFT il trasferimento DMD2
è sperimentale, come nella chat. Le impostazioni della chat non vengono cambiate
per servire una richiesta SillyTavern.
