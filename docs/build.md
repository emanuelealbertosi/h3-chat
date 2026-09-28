# Build e distribuzione Windows

Gli utenti eseguono `install.bat`: tutti i componenti sono precompilati. Python e motori CPU sono scaricati con revisioni e SHA-256 fissati; i pesi restano separati. `distribution/windows-bootstrap.zip` contiene launcher, worker nativo e interfaccia; il manifest controlla anche che i sorgenti corrispondano.

Per sviluppare servono Node.js 22+, Python 3.13 e MSVC Build Tools x64. Dalla cartella del progetto:

1. `npm ci` e `npm run build`.
2. `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/prepare-build.ps1`.
3. `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build-sd-worker.ps1`.
4. `runtime\python\python.exe -X utf8 scripts/bootstrap_bundle.py`.
5. `runtime\python\python.exe -X utf8 -m unittest discover -s tests -v` e `npm test`.

Includere nel commit il worker compilato e i due file di `distribution/` quando cambiano i rispettivi sorgenti. I fingerprint normalizzano CRLF/LF per funzionare anche con checkout Git Windows. Il bundle non contiene dati, pesi o percorsi personali.

Per un pacchetto ZIP completo eseguire anche `scripts/install_cpu.py`, `scripts/ci-install-music.py` (richiede GitHub CLI), `scripts/check_native.py` e `scripts/package.py`. La workflow di release ripete build e test su Windows, crea un archivio con manifest di tutti i file e prepara una release draft da verificare prima della pubblicazione. Il numero di versione viene letto da `h3chat/__init__.py`.
