# Modalità GPU / CPU

Lo switch GPU / CPU si trova nella barra in alto. La scelta è persistente e vale
per l'intera app, compresi i workspace ospiti. Solo l'amministratore può cambiarla.
Si cambia a coda libera, senza interrompere richieste o indicizzazioni in corso.
Il cambio libera i modelli e le cache dell'app.

**GPU** mantiene i normali motori, dispositivi e preset configurati: il nome
non forza i componenti già impostati su CPU a usare una GPU.

**CPU** disabilita creazione e modifica AI di immagini, video, musica, voce e
trascrizione, anche nei lotti, negli automatismi e nei server immagini H3.
Chat, router e Assistant possono usare un LLM locale GGUF su CPU oppure un provider esterno configurato.
Il menu LLM mostra sia i modelli locali sia i provider e permette di scegliere quello da usare in
CPU; la selezione del modello normale resta conservata. Senza un modello disponibile compare
un invito a collegarne o scaricarne uno e l'invio della chat è disabilitato.

RAG, documenti, grafica HTML/SVG, calcolo, esportazioni e Manim senza voce
restano disponibili su CPU. Le slide possono usare il LLM selezionato, immagini già
presenti, figure del RAG e diagrammi, senza nuove illustrazioni AI. Nell'infografica
sono sospese le nuove immagini, la voce e la musica generate. I montaggi e le
esportazioni di contenuti già disponibili non richiedono un modello GPU.

Anche RAG, Vision locale, trascrizione e Manim possono normalmente usare la GPU:
il controllo CPU forza i dispositivi consentiti e impedisce caricamenti dei motori multimediali. I LLM locali usano il binario
CPU, zero layer GPU, Vision CPU e motore Standard. Il RAG mantiene il modello scelto: Ovis può
richiedere molta RAM anche su CPU; EmbeddingGemma 2 è l'alternativa leggera nelle
Preferenze. L’analisi delle immagini usa Vision del LLM selezionato, se supportata;
per un LLM locale il proiettore rimane su CPU.

Il blocco è controllato dal server e prima del caricamento dei modelli;
disabilitare i soli pulsanti non sarebbe sufficiente. I parametri originali dei
modelli e dei dispositivi non vengono sovrascritti: tornano effettivi selezionando
GPU. Il dispositivo usato dal provider esterno è gestito dal provider.

In Preferenze, «Modello da configurare» serve a modificare il preset. Per
selezionarlo nella chat premi «Usa questo modello in chat e Assistant» e salva.
Anche scegliere il modello chat nel Setup aggiorna la scelta CPU attiva.
La rimozione di un modello o provider elimina le selezioni obsolete: non occorre
cancellare un provider esterno per poter scegliere un modello locale.
