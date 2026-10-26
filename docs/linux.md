# H3-Chat su Linux x64

Il pacchetto è destinato a Ubuntu 24.04 o successivo e Kali/Debian recenti,
su processori x86_64. Python, interfaccia, motori CPU/Vulkan, documenti,
trascrizione CPU, Manim e LaTeX sono inclusi. I modelli e le dipendenze Python
dei motori GPU restano separati e si installano dal Setup.

1. Scarica l'archivio `H3-Chat-VERSIONE-linux-x64.tar.gz` e il relativo `.sha256`
   dalla release ufficiale. Verifica con `sha256sum -c NOME_ARCHIVIO.sha256`.
2. Estrai tutta la cartella in una posizione scrivibile del tuo account.
3. Se mancano librerie di sistema, avvia dalla cartella estratta
   `sh Installa-dipendenze-Linux.sh`. Usa `apt` e chiede conferma con `sudo`:
   non lanciare l'applicazione come root.
4. Avvia `./Avvia-H3-Chat.sh`. L'interfaccia si apre nel browser. Per chiudere
   il servizio usa `./Ferma-H3-Chat.sh`.

Per un PC senza GPU scegli CPU e collega un LLM API, oppure un GGUF locale
compatibile con la RAM disponibile. Il RAG resta locale. I segreti API sono
protetti dal servizio Secret Service del desktop: occorre un portachiavi
utente attivo e sbloccato, per esempio GNOME Keyring.

Per NVIDIA occorrono driver compatibili; i pesi non vengono scaricati
automaticamente dal semplice avvio. Le componenti CUDA incluse non significano
che tutti i modelli entreranno nella memoria della GPU.

## Agente e cartelle

La modalità Sandbox usa `bubblewrap` e namespace Linux. Su Ubuntu con AppArmor
restrittivo, l'installer propone separatamente l'eccezione per `/usr/bin/bwrap`.
La modifica riguarda quel programma anche fuori da H3 e richiede un consenso
esplicito più `sudo`; non viene disattivato AppArmor globalmente. Senza i permessi
necessari Sandbox restituisce un errore esplicito, senza eseguire fuori isolamento.

H3 e Globale hanno permessi distinti. I privilegi amministratore per i comandi
dell'Agente richiedono la conferma nativa; Autoapprova non la sostituisce.

## Aggiornamenti

Ferma tutti i lavori e il servizio, estrai il nuovo pacchetto in una cartella
nuova e trasferisci la cartella `data` dalla precedente installazione, mantenendo
una copia di sicurezza. I collegamenti a modelli fuori dall'app restano validi
se i loro percorsi non cambiano. Conserva l'intera vecchia installazione finché
non hai verificato chat e impostazioni nella nuova.
