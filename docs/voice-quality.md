# Higgs: precisione, qualità e tempi

In **Impostazioni → Preferenze → Voice → Precisione GPU Higgs** puoi scegliere:

- **4 bit:** pesi quantizzati per risparmiare memoria, circa 5,5 GB liberi richiesti.
- **8 bit:** compromesso per schede più piccole, circa 7 GB liberi richiesti. Rimane il default delle nuove installazioni.
- **BF16:** pesi senza quantizzazione, circa 12 GB liberi richiesti, inclusa una riserva per codec e sintesi.

Sono stime, non garanzie per ogni modello o segmento. Il motore controlla la VRAM libera prima del caricamento e non cambia automaticamente la precisione scelta. La rigenerazione usa la precisione attualmente impostata, conservando campione, seed e controlli di recitazione della richiesta.

Higgs Audio v3 è autoregressivo: non usa step di diffusione come i generatori di immagini. Ogni passo produce token audio dipendenti dai precedenti; aumentarne il limite non migliora una frase già completa. H3-Chat attende il segnale di fine frase e rifiuta un segmento che termina solo perché ha esaurito il limite.

La temperatura modifica la variabilità del campionamento, non la precisione dei pesi. Campione vocale, trascrizione, lingua e indicazioni di recitazione influiscono sulla pronuncia e sull'espressività. BF16 non garantisce una voce più naturale: confronta lo stesso testo, campione e seed prima di valutarlo.

Il motore conserva i token sul dispositivo di sintesi fino alla conversione in audio, evitando le copie sulla CPU a ogni passo. Il controllo di fine frase continua a sincronizzare il campionamento, quindi la GPU può restare sotto il massimo utilizzo.

Con **Avanzate** attivo in chat, **Tempi della voce** mostra il tempo totale, il caricamento, la preparazione del campione e delle frasi, la sintesi e la conversione audio. Sono tempi di elaborazione, distinti dalla durata del file audio. Il totale include anche variazioni di ritmo e scrittura dei file.

## Confronto sul PC di prova

Misura dell'8 ottobre 2026 su RTX 5070 Ti, Higgs v3 Transformers, stesso testo italiano, campione, seed 734 e temperatura 0,7. Tempi della seconda sintesi per ciascun processo, con modello già caricato:

| Configurazione | Tempo di sintesi | Durata del parlato |
| --- | ---: | ---: |
| 8 bit precedente | 55,0 s | 8,52 s |
| 8 bit, token mantenuti sulla GPU | 55,1 s | 8,52 s |
| BF16, token mantenuti sulla GPU | 16,0 s | 8,32 s |

In questo test BF16 genera circa 3,4 volte più fotogrammi audio al secondo. La rimozione delle copie per passo non dà un vantaggio misurabile a 8 bit: token e waveform prima e dopo sono identici. Il passaggio a BF16 cambia il campionamento e va valutato anche all'ascolto. Questi numeri non garantiscono lo stesso guadagno su altre GPU, precisioni, campioni o testi. Il caricamento è misurato separatamente, perché dipende anche dalla cache dei file.

Fonti: [adattatore Transformers usato da H3-Chat](https://huggingface.co/multimodalart/higgs-audio-v3-tts-4b-transformers/blob/main/modeling_higgs_multimodal_qwen3.py), [quantizzazione bitsandbytes](https://huggingface.co/docs/transformers/quantization/bitsandbytes).
