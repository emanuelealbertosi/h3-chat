# Modalità GPU / CPU

Lo switch GPU / CPU si trova nella barra in alto. La scelta è persistente e vale
per l'intera app, compresi i workspace ospiti. Solo l'amministratore può cambiarla.
Si cambia a coda libera, senza interrompere richieste o indicizzazioni in corso.
Il cambio libera i modelli e le cache dell'app.

**GPU** mantiene i normali motori, dispositivi e preset configurati: il nome
non forza i componenti già impostati su CPU a usare una GPU.

**CPU** disabilita creazione e modifica AI di immagini, video, musica, voce e
trascrizione, anche nei lotti, negli automatismi e nei server immagini H3.
Chat, router e Assistant richiedono un provider LLM esterno configurato.
Se ne esistono più di uno, il menu LLM permette di scegliere quello da usare in
CPU; la selezione del modello normale resta conservata. Senza provider compare
un invito a configurarlo e l'invio della chat è disabilitato.

RAG, documenti, grafica HTML/SVG, calcolo, esportazioni e Manim senza voce
restano disponibili su CPU. Le slide possono usare il LLM esterno, immagini già
presenti, figure del RAG e diagrammi, senza nuove illustrazioni AI. Nell'infografica
sono sospese le nuove immagini, la voce e la musica generate. I montaggi e le
esportazioni di contenuti già disponibili non richiedono un modello GPU.

Anche RAG, Vision locale, trascrizione e Manim possono normalmente usare la GPU:
il controllo CPU forza i dispositivi consentiti e impedisce caricamenti locali
del LLM e dei motori multimediali. Il RAG mantiene il modello scelto: Ovis può
richiedere molta RAM anche su CPU; EmbeddingGemma 2 è l'alternativa leggera nelle
Preferenze. L'analisi delle immagini della chat usa Vision del provider esterno,
se supportata dal modello selezionato.

Il blocco è controllato dal server e prima del caricamento dei modelli;
disabilitare i soli pulsanti non sarebbe sufficiente. I parametri originali dei
modelli e dei dispositivi non vengono sovrascritti: tornano effettivi selezionando
GPU. Il dispositivo usato dal provider esterno è gestito dal provider.
