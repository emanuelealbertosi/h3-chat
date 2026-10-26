#!/bin/sh
# Exact AppArmor exception authorized by the user on 2026-10-26.
# Never disable AppArmor or the global unprivileged-userns restriction.
set -eu
if [ "$(cat /proc/sys/kernel/apparmor_restrict_unprivileged_userns 2>/dev/null || echo 0)" != 1 ]; then exit 0; fi
for profile in /etc/apparmor.d/bwrap /etc/apparmor.d/usr.bin.bwrap /etc/apparmor.d/bubblewrap; do
  if [ -f "$profile" ]; then printf 'Profilo bubblewrap di sistema già presente: %s\n' "$profile"; exit 0; fi
done
if [ "${1:-}" != '--ci' ]; then
  printf '%s\n' 'Ubuntu richiede di autorizzare bubblewrap a preparare l’isolamento di Agent.' \
    'Verrà aggiunto un profilo flags=(unconfined) per /usr/bin/bwrap, anche per utilizzi esterni a H3.' \
    'AppArmor e il limite userns globale restano attivi. I programmi Agent restano nei namespace isolati di H3.'
  printf 'Installare questo profilo? [s/N] '
  read -r answer
  case "$answer" in s|S|si|SI) ;; *) echo 'Profilo non installato: Agent Sandbox non è disponibile finché bubblewrap non può avviarsi.'; exit 0;; esac
fi
file=$(mktemp)
trap 'rm -f "$file"' EXIT HUP INT TERM
cat > "$file" <<'PROFILE'
abi <abi/4.0>,
include <tunables/global>
profile h3-chat-bwrap /usr/bin/bwrap flags=(unconfined) {
  userns,
}
PROFILE
target=/etc/apparmor.d/h3-chat-bwrap
if [ -f "$target" ]; then
  if cmp -s "$file" "$target"; then echo 'Profilo H3 bubblewrap già installato.'; exit 0; fi
  echo 'Il profilo H3 esistente è diverso: nessuna sovrascrittura automatica.' >&2; exit 1
fi
sudo install -m 644 "$file" "$target"
sudo apparmor_parser -r "$target"
printf '%s\n' 'Profilo per bubblewrap installato. Nessuna modifica al limite userns globale.'
