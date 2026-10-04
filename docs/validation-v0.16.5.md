# Verifica della versione 0.16.5

Le prove native sono state eseguite su Windows con dati sintetici. I modelli
e i campioni vocali sono letti da percorsi locali e non inclusi nel pacchetto.
Sono passati 288 test Python e 7 test JavaScript; il bundle distribuito
corrisponde ai sorgenti dell'interfaccia.

- Ovis ufficiale: tutti gli 11 file verificati con SHA-256. Inferenza reale
  CPU e GPU, vettori di 2048 dimensioni e tre interrogazioni in italiano:
  documento pertinente al primo posto in tutti i casi. Coseno minimo tra
  risultati CPU/GPU: 0,99929. Il RAG indicizza testo estratto, non media grezzi.
- Voice: sintesi reale su GPU a 4 e 8 bit e CPU float32, WAV mono a 24 kHz
  terminati correttamente. Il motore e il codec sono interni a H3-Chat.
  Le indicazioni di recitazione dipendono dalla risposta del modello.
- Manim completo: rendering reale di scena 3D, testo, immagini e MathTex;
  lettura/scrittura di file privati e rete negate; interruzione del renderer
  e dei processi figli verificata. Ogni tentativo ha il proprio tempo massimo.
- Montaggio: due clip sintetici uniti su una traccia di 2,5 secondi e una
  animazione adattata alla stessa traccia. Durata e tono originale verificati
  nell'AAC decodificato; i file di ingresso restano invariati.
- MiniMax Hybrid: due clip nativi da un secondo, 0,2 MP e un passo, con
  memoria visiva della prima scena passata alla seconda. La suddivisione
  42 secondi = 15 + 15 + 12, gli intervalli audio e il montaggio sono anche
  verificati dai test di orchestrazione. Questa prova breve non misura la
  qualità o le prestazioni dei video completi da 15 secondi e 0,7 MP.
  Nel test il caricamento dei pesi ha richiesto circa 75–79 secondi per scena;
  non viene dichiarata una parità di velocità con ComfyUI.
- Interfaccia: selettore LLM in chat, salvataggio dei parametri per modello,
  controlli Voice, impostazioni CPU e layout a 390 px verificati nel browser
  con conversazioni sintetiche, senza errori JavaScript.

Il video con audio e memoria è limitato a dieci minuti e al motore MiniMax
standalone. I server esterni continuano a supportare i clip ordinari.
