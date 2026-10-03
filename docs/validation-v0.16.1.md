# Verifica 0.16.1

Completa l'export PowerPoint introdotto in 0.16.0. La build 0.16.0 è stata
interrotta prima della pubblicazione del pacchetto; la release scaricabile
con tutte le funzioni slide è 0.16.1.

- Formule inline: dimensioni prese dal rettangolo reale, non dal clientWidth
  nullo degli elementi inline. Una superficie HTML misura e rasterizza anche
  SVG e KaTeX; gli elementi annidati delle formule non vengono duplicati.
- Testi nativi: nessun ritorno a capo aggiuntivo all'interno di una riga già
  composta; i segmenti separati da una formula conservano le loro posizioni.
- La fixture contiene una figura colorata riconoscibile. Il test browser
  esporta formula, diagramma e figura e controlla che tutte e tre le immagini
  incorporate contengano pixel visibili, oltre ai precedenti controlli.
- Microsoft PowerPoint apre e renderizza la fixture 4:3: formula leggibile,
  diagramma con freccia e figura colorata, titoli senza parole spezzate.
  La validazione di schema, relazioni e parti grafiche è passata.
- Il collaudo con pagine dense e grafici nativi resta valido: tutte le parole,
  righe di codice e voci degli elenchi sono conservate. I grafici nativi hanno
  coordinate corrette; l'editor salva e recupera le modifiche.

Restano applicabili i controlli e i limiti descritti in validation-v0.16.0.md.
