# Permessi di avvio proposti per la Sandbox Mac

Le sonde native eseguono soltanto `true`, `sh` e Python con una stampa di prova.
Tutti si arrestano nell'inizializzazione con il profilo restrittivo corrente.
L'auto-ispezione `Sandbox` syscall 67 è stata aggiunta e non basta da sola.

Proposta da autorizzare, prima di applicarla e collaudarla:

```scheme
(allow mach-lookup
  (global-name "com.apple.secinitd")
  (global-name "com.apple.system.opendirectoryd.libinfo")
  (global-name "com.apple.system.logger")
  (global-name "com.apple.logd"))
(allow file-read-data file-write-data (subpath "/dev/fd"))
(allow file-read* (literal "/"))
```

I servizi gestiscono inizializzazione del processo, identità dell'utente e log.
`/dev/fd` permette comunicazione attraverso i soli descrittori già ereditati;
il broker passa esclusivamente pipe anonime e chiude gli altri descrittori.
La radice `/` è la sola directory radice, non una regola ricorsiva sul disco.

Non sono proposti accesso a Portachiavi, Apple Events/Launch Services, accesso
generale a Mach, rete diretta o lettura/scrittura di documenti esterni alla
cartella scelta. Questi permessi di inizializzazione vanno verificati con
canary esterni, rete locale bloccata e processi figli, prima della distribuzione.

Riferimento tecnico primario: il profilo minimo di piattaforma di
[Codex](https://github.com/openai/codex/blob/main/codex-rs/sandboxing/src/seatbelt_read_only_platform_defaults.sbpl).
Le regole proposte sono un sottoinsieme; non viene adottato il suo accesso più
ampio ai file di sistema.
