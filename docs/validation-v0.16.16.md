# Verifica 0.16.16

- 339 test Python completati, inclusi messaggi HTTP locali multimodali, piano e
  singole scene Voice+Manim con figure RAG, streaming HTML e compatibilità dei
  deck precedenti. Log locale: `work/tests-v01616-final.log`.
- 10 test JavaScript superati. Collaudi Edge su dati sintetici: nuovo HTML/CSS,
  SVG, formule LaTeX, colori originali, isolamento degli script e della rete,
  modifica testo/font, import e sostituzione immagini da PC/RAG, salvataggio e
  riapertura, HTML/PDF/PPTX e layout mobile.
- `tests/browser-slides-html.mjs` controlla anche testi nativi modificabili e
  colori nel PPTX. I container main/section/aside/header/footer mantengono il
  layout nella sanitizzazione PDF/HTML. I gradienti PPTX sono oggetti grafici.
- `tests/browser-slides.mjs`, `tests/browser-slide-design.mjs` e
  `tests/browser-vision-device.mjs`: regressioni del precedente generatore,
  editor deterministico, formule/diagrammi, navigazione, cronologia, export e
  scelta/persistenza CPU/GPU Vision.
- Ricerca Wikimedia verificata anche con una richiesta reale all'API pubblica;
  test di import preservano autore/licenza e negano indirizzi non autorizzati.
  Le figure RAG sono limitate al progetto della chat e vengono importate tramite
  worker isolato con le dipendenze Documenti già distribuite.
- Bundle precompilato aggiornato per installazione da clone senza compilatori.
  Il pacchetto Windows esclude chat, documenti, credenziali e pesi personali.

Queste prove verificano il funzionamento del percorso applicativo. Le scene e
le slide dei collaudi usano risposte sintetiche: non certificano la qualità
artistica di ogni LLM o il successo del rendering di ogni codice Manim generato.
Gradienti, immagini di sfondo e grafici SVG richiedono verifica visiva del
contrasto; gli elementi oltre i bordi vengono segnalati nel canvas HTML.
