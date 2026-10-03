# Verifica 0.16.2

268 test Python e 7 test JavaScript passati. Collaudi browser sintetici per
slide progressive, design/editor/export, contrasto, audio e recupero Manim.

- Contrasto automatico sullo sfondo composito: tre temi per tre stili,
  copertina, tabelle, codice evidenziato, formule, pannelli annidati,
  trasparenza, opacità e colori modificati nell'editor. Misurazione browser
  indipendente delle scritte, dei pixel testuali Chart.js e dei testi Mermaid.
  I testi vengono corretti a un rapporto di almeno 4,5:1 nelle superfici
  supportate. Nessuna dichiarazione di conformità completa dell'app.
- PDF e PowerPoint esportati dalla fixture; schema PPTX validato e apertura
  reale con Microsoft PowerPoint. Testi e grafici dati restano modificabili;
  anche gli sfondi dei titoli grafici e del codice inline vengono conservati.
- Audio: WAV sintetico di un secondo convertito realmente in MP3 e di nuovo
  in WAV, verifica durata, canali, frequenza e segnale. Originale invariato,
  cache senza nuova codifica, input non valido e percorsi fuori dalla cartella
  dati respinti. Download browser WAV/MP3 in chat e canvas, ripristino dopo
  ricaricamento e protezione token/identità media verificati.
- Encoder incluso nella libreria PyAV 19.0.0 Windows già fissata nel manifest,
  ora anche nei componenti installati per impostazione predefinita. Nessun
  download di modelli, eseguibile FFmpeg esterno o calcolo GPU per gli export.
- Manim: durata richiesta come obiettivo; un MP4 valido resta disponibile
  anche se dura 28 s rispetto ai 20 s richiesti, senza un'altra chiamata LLM.
  Recupero dei vecchi errori di sola durata, con controllo chat/messaggio e
  percorso dell'output; preserva eventuali documenti successivi nel canvas.
- Video: tempi dell'ultimo passo visibili durante l'attesa; riepilogo e tempi
  delle singole fasi disponibili anche con Avanzate disattivato. Il percorso
  GPU/offload e il contenuto del video non sono cambiati.
- Test sintetico sulla RTX 5070 Ti: attenzione con 83.000 token, 56 teste da
  128, BF16 e layout QKV del modello. Prove ripetute: 8/4/2 suddivisioni circa
  0,74–0,76 s per chiamata; memoria di picco 5.036/5.533/6.528 MiB. Ridurre
  le suddivisioni non offre un guadagno stabile e non è stato imposto.
  Questa è una misura della sola attenzione, non del rendering completo;
  non dimostra equivalenza o parità di velocità con ComfyUI.
