# Verifiche H3-Chat 0.10.0

Collaudo locale su Windows, RTX 5070 Ti 16 GB e circa 40 GB di RAM. Sono stati
usati i file originali dei modelli, con diffusore standard H3 pruned INT8 FL2VA,
encoder Qwen3-VL H3 NVFP4/AWQ, VAE video INT8/ConvRot e VAE audio FP32. Nessun
server ComfyUI o H3-Studio era necessario al processo di generazione.

- **122 test Python** e **2 test JavaScript** superati. Coprono anche selezione
  esplicita/automatica video, precedenza rispetto alla musica, negazioni e richieste
  testuali, percorsi esterni, preset per modello, token Assistant per LLM,
  snapshot dei lavori, annullamento/riuso del processo, validazione degli allegati,
  ruoli/tempi/indici, audio e MP4 con byte range, destinazione canvas e assenza di
  caricamento LLM con Assistant Off.
- **Interfaccia in Chrome headless:** Video/Music si escludono; il browser MiniMax
  mostra i quattro file richiesti; Avanzate mostra 15 s / 0,7 MP; due preset video
  distinti mantengono i rispettivi passi anche dopo cambio selezione e salvataggio.
  Nessun errore JavaScript durante il controllo.
- **Runtime privato:** import dei moduli H3, sampler e codec; scrittura/lettura
  H.264/AAC senza eseguibile FFmpeg esterno; conservazione del sample rate di una
  sorgente esatta a 48 kHz; resampling dei riferimenti a 32 kHz; riferimento audio
  breve accettato e traccia esatta troppo breve rifiutata.
- **Generazione GPU completa:** 15 s, 0,7 MP, 1152×640, CFG 1, 8 passi Res
  Multistep/Simple, shift video 12/audio 3, seed 42, offload attivo. Il modello ha
  campionato 362 frame; MP4 verificato con **360 frame a 24 fps, durata esatta
  15,000 s, video H.264 e audio AAC**. Fotogramma centrale controllato visivamente.
  Tempo totale 1037,6 s (circa 17 min 18 s): lettura/trasferimenti e generazione
  restano costosi con questi pesi e questa risoluzione. Encoder H3, diffusore e VAE
  sono stati eseguiti su CUDA; pesi inattivi offloaded in RAM.
- **Condizionamento combinato GPU:** clip di 1 s / 0,2 MP / 8 passi con tre immagini
  (frame iniziale, frame intermedio a 0,5 s e riferimento), più audio originale
  inserito sia come riferimento sia nel latent target con noise mask audio zero.
  MP4 con 24 frame e durata esatta 1 s; correlazione audio sorgente/decodificato AAC
  0,9969. Questo verifica il percorso audio per reuse/lip-sync e i ruoli combinati;
  non misura l’accuratezza visiva del movimento labiale su un volto parlante.
- **Pacchetto Windows locale:** estratto in una nuova directory, manifest SHA-256
  controllato, bundle precompilato installato, versione 0.10.0 e API di stato
  verificate. Worker video/musica avviati con il runtime privato; probe DLL CPU
  verifica ABI e provenienza app-local dei CRT Microsoft. Nessun dato personale,
  peso di modello o output di collaudo incluso nel pacchetto.

I test del servizio usano dati temporanei e mock per le generazioni dove indicato;
le due generazioni descritte sopra sono inferenze reali. Il collaudo su un modello
e una GPU non certifica ogni variante H3 o configurazione hardware. La qualità di
dialoghi, suoni, riferimenti e sincronizzazione visiva resta dipendente dal modello.
