# Verifica 0.16.12 · riferimenti vocali e pronuncia

## Correzione

Il worker preparava il riferimento con il downmix e il ricampionatore di
FFmpeg/PyAV, mentre H3-Audio media i canali e applica il filtro sinc di Higgs.
La preparazione ora usa il secondo percorso, mantenendo PyAV per la sola
decodifica e senza aggiungere dipendenze da H3-Audio o dai suoi servizi.

Gli identificatori dei campioni base corrispondono alle voci di H3-Audio;
il loro seed usa lo stesso hash nell’intervallo a 31 bit. I campioni personalizzati
usano un’identità derivata dal nome, indipendente dalla cartella di installazione.
I metadati della sintesi registrano nome del riferimento e identità applicata.

Il modello selezionato non espone un parametro di lingua nel suo protocollo
TTS: nessuna falsa istruzione linguistica viene inserita nel testo da pronunciare.
Setup e documentazione spiegano che l’accento dipende anche dal riferimento e
che per l’italiano è preferibile un campione italiano con trascrizione fedele.

## Controlli

- **310 test Python** superati su Windows, incluse le regressioni Voice/Manim.
- **7 test JavaScript** superati; UI e bundle per installazioni da clone ricostruiti.
- Prova nativa su stereo PCM 44,1 kHz: forma d’onda identica alla media dei
  canali seguita dal sinc a 24 kHz; canali in opposizione si annullano.
- Verificati padding dei campioni brevi, rifiuto di riferimenti vuoti o oltre
  30 secondi e stabilità dell’identità in cartelle differenti.
- Sintesi Higgs reale GPU a 8 bit con riferimento femminile italiano e
  controlli di registro/interpretazione mantenuti. I primi 15,64 s del nuovo
  parlato vengono trascritti in italiano senza errori nelle due frasi verificate.

La trascrizione è un controllo automatico di lingua e contenuto, non una misura
oggettiva della naturalezza o dell’accento. I campioni vocali, i dati delle chat
e i risultati locali non vengono inclusi nel pacchetto pubblico.
