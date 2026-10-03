# Verifica 0.16.4

- 272 test Python e 7 JavaScript superati.
- Output selezionabile fino a 100.000 token: valori correnti e preset iniziali
  invariati; salvataggio, cambio modello, ripristino preset e trasmissione del
  limite al provider API verificati. Il vincolo di metà del contesto resta.
- Browser desktop/mobile con provider sintetico: massimo del campo 100.000,
  valore iniziale 1.024 invariato, salvataggio e riapertura con 100.000.
- Generazione Manim conserva il thinking scelto. Risposte strutturate locali
  mantengono la temperatura configurata; il router resta a temperatura zero.
- Rigenera usa il LLM e i relativi parametri attuali, mantenendo richiesta,
  allegati, fonti e controlli delle altre modalità dal lavoro originale.
- Runtime Manim Community 0.21.0: verificata la presenza delle API di camera,
  3D, superfici, tracker, updater, trasformazioni e LaTeX.
- Rendering reale sintetico: scena 3D, camera in movimento, trasformazione,
  immagine e MathTex generano un MP4 valido. Isolamento e cancellazione dei
  discendenti verificati. Nessuna chat dell’utente letta o riprodotta.

Le istruzioni per ricreare chiedono una nuova composizione visiva; la qualità
effettiva e la varietà del codice dipendono dal modello. Nessuna accelerazione
video o compatibilità Ovis dichiarata in questa versione.
