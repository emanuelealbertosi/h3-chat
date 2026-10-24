# Build e distribuzione Windows

Gli utenti eseguono `install.bat`: tutti i componenti sono precompilati. Python e motori CPU sono scaricati con revisioni e SHA-256 fissati; i pesi restano separati. `distribution/windows-bootstrap.zip` contiene launcher, worker nativo e interfaccia; il manifest controlla anche che i sorgenti corrispondano.

Per un PC senza GPU che usa soltanto modelli esterni, **Installa-API-senza-GPU.bat**
richiama `scripts/install.ps1 -ApiOnly` (`scripts/install.py --api-only`): salta
i motori CPU generativi e tutte le loro verifiche, mantenendo strumenti documenti.
Scrive solo il marker `runtime/installation-profile.json`; il servizio ne usa i
default CPU/API quando crea un nuovo database. I database esistenti non vengono
modificati. Gli embedding RAG si installano separatamente nelle Preferenze.

Per sviluppare servono Node.js 22+, Python 3.13 e MSVC Build Tools x64. Dalla cartella del progetto:

1. `npm ci` e `npm run build`.
2. `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/prepare-build.ps1`.
3. `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build-sd-worker.ps1`.
4. `runtime\python\python.exe -X utf8 scripts/bootstrap_bundle.py`.
5. `runtime\python\python.exe -X utf8 -m unittest discover -s tests -v` e `npm test`.

Includere nel commit il worker compilato e i due file di `distribution/` quando cambiano i rispettivi sorgenti. I fingerprint normalizzano CRLF/LF per funzionare anche con checkout Git Windows. Il bundle non contiene dati, pesi o percorsi personali.

Per un pacchetto ZIP completo eseguire anche `scripts/install_cpu.py`, `scripts/ci-install-music.py` (richiede GitHub CLI), `scripts/check_native.py` e `scripts/package.py`. La workflow di release verifica prima l'installazione API senza motori GPU e poi quella completa, ripete build e test su Windows, crea un archivio con manifest di tutti i file e prepara una release draft da verificare prima della pubblicazione. Il numero di versione viene letto da `h3chat/__init__.py`.


## macOS Apple Silicon

La workflow `macos.yml` costruisce su `macos-15` arm64 una distribuzione portatile con Python, llama.cpp CPU/Metal, strumenti documenti e browser PDF inclusi. `scripts/build_macos.py` usa gli archivi ufficiali fissati in `scripts/macos-sources.json`; `scripts/check_macos.py` verifica i componenti effettivamente distribuiti e l'eseguibile `.app` dopo una rilocazione con spazi nel percorso, sempre con dati temporanei. Il pacchetto esclude cache, profili utente, database, cartelle data/models/work e dipendenze Windows. Modelli GGUF reali non vengono scaricati né caricati dal test di avvio nativo.

La workflow di release chiama anche la build Mac e allega il relativo archivio, checksum e rapporto al draft soltanto se entrambe le piattaforme passano. La pubblicazione del draft richiede la verifica dei rapporti di entrambi i pacchetti. Le release già pubblicate non vengono sovrascritte.
