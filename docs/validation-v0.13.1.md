# H3-Chat 0.13.1 — accesso Tailscale

All’avvio l’app rileva Tailscale e riutilizza o configura un proxy HTTPS privato
verso la propria porta locale. Il server continua ad ascoltare su loopback.
Non vengono modificati proxy di altre applicazioni, percorsi aggiuntivi o Funnel.
L’indirizzo è mostrato nei log e nelle impostazioni, con copia e riprova.
Riaprendo l’app dopo aver connesso Tailscale si riprova senza riavviare il motore.

Verifiche eseguite su Windows:

- 195 test Python e 2 test JavaScript.
- Proxy Tailscale Serve reale con certificato HTTPS verificato: health, stato,
  creazione chat con token e download di un file.
- Origin non autorizzata respinta attraverso lo stesso proxy HTTPS.
- I proxy esistenti e le impostazioni Funnel sono identici prima e dopo la prova.
  Il solo proxy temporaneo usato per la verifica è stato rimosso.
- Test dedicati: Tailscale assente/scollegato/in errore, conservazione degli altri
  servizi, porte occupate, Funnel non fidato, verifica del proxy dopo la creazione,
  Host/Origin/CSRF e riapertura dell’app con rete inizialmente non disponibile.

Non è una nuova implementazione dei motori di generazione: restano quelli della
0.13.0. Tutte le operazioni dell’interfaccia, incluse impostazioni e scelta dei
file locali, sono disponibili ai dispositivi autorizzati della propria tailnet.
L’accesso da un secondo dispositivo dipende anche dalle regole Tailscale della rete.
