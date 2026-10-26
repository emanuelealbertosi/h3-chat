# Ubuntu: autorizzazione per l'avvio di Agent Sandbox

Stato: autorizzata dall'utente il 26 ottobre 2026: «Sì: collaudo e opzione esplicita
nell’installer». La revisione automatica aveva respinto l'installazione senza questo
consenso specifico. Nessuna modifica a Windows, Mac o al PC attuale. Il profilo è
previsto per le VM di collaudo e come scelta amministratore nell'installer Linux.

La sonda Ubuntu 24.04 in GitHub Actions ha registrato AppArmor DENIED per setpcap
e net_admin durante la preparazione dei namespace di /usr/bin/bwrap. Il programma
generato non era ancora partito. La medesima operazione fallisce anche eseguendo
bubblewrap senza H3. Non è un errore del modello.

La proposta è una eccezione per il solo eseguibile di sistema /usr/bin/bwrap:

```text
abi <abi/4.0>,
include <tunables/global>
profile h3-chat-bwrap /usr/bin/bwrap flags=(unconfined) {
  userns,
}
```

Il profilo sarebbe installato come /etc/apparmor.d/h3-chat-bwrap, con privilegi
amministratore e conferma esplicita nell'installer Linux. Si applicherebbe a
qualsiasi utilizzo di /usr/bin/bwrap, non soltanto a H3. flags=(unconfined) esenta
bubblewrap dalla restrizione AppArmor aggiuntiva durante la creazione dei namespace.
H3 continuerebbe a richiedere il filesystem isolato, rete separata, PID namespace,
capabilities rimosse e nessun ripiego su esecuzione non isolata. Questo non rende
equivalenti l'eccezione di sistema e le verifiche di H3.

Non si disabilitano AppArmor o il limite userns globale. Un profilo bubblewrap già
fornito dalla distribuzione non verrebbe sovrascritto. L'alternativa è mantenere
disponibile Agent H3 e Globale dove supportato, segnalando Sandbox non disponibile
finché bubblewrap non supera una sonda reale di avvio.

Il consenso richiesto riguarda sia il collaudo su VM GitHub usa-e-getta sia la
presenza di questa opzione esplicita nell'installer. Sul PC dell'utente
l'installazione resterebbe una scelta amministratore separata.
