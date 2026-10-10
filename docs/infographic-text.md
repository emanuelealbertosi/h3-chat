# Scritte animate nelle infografiche

Seleziona **Infografica → Impostazioni → Scritte ed effetti**. Le scelte iniziali sono automatiche: il modello continua a comporre HTML e a scegliere la regia seguendo il prompt.

- **Comparsa:** dissolvenza, scorrimento, bump/rimbalzo, carattere per carattere, lettere in caduta con prospettiva, onda di lettere e rotazione 3D.
- **Direzione:** da sinistra, destra, alto o basso per lo scorrimento.
- **Velocità:** dal modello, lenta, normale o veloce. Riguarda la comparsa delle scritte, senza cambiare voce o durata del filmato.
- **Aspetto:** dal modello, pulito, neon o contorno.
- **Colore:** dal modello, un colore scelto oppure passaggio fra due colori durante la scena. Il secondo colore controlla anche la luce neon e il contorno.
- **Applica a:** titoli e parole chiave, oppure tutti i testi.

Le opzioni esplicite vengono applicate dal motore e conservano gli ingressi/uscite decisi dall’LLM. Immagini, video, riquadri e impaginazione restano indipendenti. Usa effetti a lettere su brevi titoli; testi troppo lunghi o formule usano una dissolvenza per mantenere il rendering leggero e la composizione integra.

Nel **canvas → Scritte ed effetti** puoi cambiare queste scelte per un’infografica già creata. Sono valide per tutte le scene. **Tempi degli elementi** apre una seconda modale per cambiare effetto e tempi di un singolo elemento; un effetto esplicito qui prevale sul preset generale. Seleziona **Dal modello / impostazioni** per ripristinare la regia generale.

Premi **Anteprima** per vedere il risultato. Il filmato già esportato resta quello precedente fino a **Esporta / aggiorna MP4**: il nuovo rendering usa gli stessi effetti dell’anteprima, con voce e musica conservate.

Esempio di prompt con impostazioni automatiche:

> Crea un’infografica verticale con i video allegati. Il titolo entra da sinistra, lo slogan compare lettera per lettera come se le lettere cadessero dall’alto con prospettiva, la frase finale fa un piccolo bump. Usa neon ciano per le parole chiave, senza strobo. Sincronizza gli ingressi con la narrazione e lascia tempo per leggere.
