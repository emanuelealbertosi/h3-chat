# Qualità musicale

In **Impostazioni → Musica → Qualità musicale** collega due modelli già presenti sul computer:

| Preset | Modello consigliato | Passi iniziali |
| --- | --- | --- |
| Alta | YuE2 3B BF16 | 60 |
| Bassa | YuE2 3B Q8_0 | 32 |

Usa **Sfoglia e collega YuE2** per scegliere pesi, VAE e cartella con sidecars. Quindi assegna il modello collegato al preset Alta o Bassa. I percorsi sono configurabili su ogni installazione; nessun file viene copiato o scaricato scegliendo la qualità.

I due preset mantengono il VAE scelto nel collegamento, normalmente FP16. Non convertono i pesi: scegliere BF16 significa caricare realmente il file BF16. Alta richiede più memoria per i pesi e più tempo per la sintesi.

Puoi modificare il modello e i passi di entrambi i preset. Gli altri parametri (CFG, seed, pianificazione, campionamento) restano quelli specifici del modello in Avanzate. La scelta **Parametri del modello** conserva integralmente il comportamento precedente.

In chat, seleziona **Music → Impostazioni → Qualità musicale → Alta / Bassa**. **Predefinita** segue la qualità scelta dall’amministratore. Il riepilogo mostra modello effettivo e passi. La stessa configurazione viene usata dal routing musicale automatico e dalla musica generata per le infografiche.

Ogni richiesta salva modello e passi prima di entrare in coda. Cambiare preferenze non modifica lavori già accodati; Rigenera ripete il preset catturato. Le impostazioni TTS della voce narrata sono separate.

## Durata massima opzionale

In **Music → Impostazioni** attiva **Imposta durata massima per questa richiesta** e inserisci i secondi (`max_duration`, da 0,04 a 900). Il controllo è disattivato di default. Senza override segue il preset del modello, che inizialmente non applica questo parametro. Puoi anche salvare un limite per ciascun modello in **Impostazioni → Musica → Preset del modello** e disattivarlo nuovamente.

Il parametro viaggia nella richiesta di generazione, separato da Style Prompt e Lyrics. È un tetto, non una durata obbligatoria: YuE2 può terminare prima. Come nel [nodo ufficiale YuE2GenerateMusic](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_extras/nodes_yue2.py), il motore standalone traduce i secondi in un massimo di token musicali a 25 frame al secondo **prima** dell’inferenza; non genera un brano lungo per poi tagliarlo. Quando attivo, questo valore sostituisce il limite dei token audio e riduce il minimo se necessario. Quando disattivato, i limiti precedenti restano invariati. I server H3 ricevono `parameters.max_duration`.

La richiesta in coda e Rigenera conservano il valore originale. **Riutilizza** ripristina la scelta nel pannello Music. I passi Alta/Bassa e la composizione restano invariati.
