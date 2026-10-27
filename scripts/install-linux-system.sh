#!/bin/sh
set -eu
if [ "$(id -u)" = 0 ]; then
  echo 'Avvia questo installer come utente normale: sudo chiederà conferma per le dipendenze.' >&2
  exit 1
fi
if ! command -v apt-get >/dev/null 2>&1; then
  echo 'Pacchetto supportato su Ubuntu 24.04+ e Kali/Debian recenti con apt.' >&2
  exit 1
fi
sudo apt-get update
sudo apt-get install -y bubblewrap polkitd pkexec gnome-keyring libsecret-1-0 libnss3 libatk1.0-0 libatk-bridge2.0-0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libxkbcommon0 libcairo2 libpango-1.0-0 libasound2t64 libgomp1 libvulkan1 build-essential
sh "$(dirname "$0")/install-linux-sandbox.sh"
printf '\nDipendenze installate. Apri Avvia-H3-Chat.sh come utente normale.\n'
