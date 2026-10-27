#!/bin/bash
# CI only: official Kali userland, private mounts, ordinary-user H3 checks.
set -euo pipefail
if [[ ${GITHUB_ACTIONS:-} != true || ${RUNNER_OS:-} != Linux ]]; then
  echo 'This native test helper runs only on a disposable Linux CI runner.' >&2; exit 1
fi
root="$PWD/build/kali-root"
if [[ -e "$root" ]]; then echo 'Refusing to overwrite an existing Kali test root.' >&2; exit 1; fi
mkdir -p "$root"
container=$(docker create kalilinux/kali-rolling)
trap 'docker rm "$container" >/dev/null 2>&1 || true' EXIT
docker export "$container" | sudo tar --no-same-owner -xf - -C "$root"
test -d "$root/etc" && test ! -L "$root/etc"
sudo cp --remove-destination -L -- /etc/resolv.conf "$root/etc/resolv.conf"
# No Docker masked-/proc restriction is inherited. Mounts disappear when this
# private mount namespace exits; no user workstation or global sysctl is touched.
sudo unshare --mount --propagation private -- /bin/bash -s -- "$root" "$PWD" <<'HOST'
set -euo pipefail
root=$1;source=$2
mount --make-rprivate /
mount --bind /dev "$root/dev"
mount -t proc proc "$root/proc"
mkdir -p "$root/h3-input/scripts" "$root/h3-input/build/kali-input"
mount --bind "$source/scripts" "$root/h3-input/scripts"
mount -o remount,bind,ro "$root/h3-input/scripts"
mount --bind "$source/build/kali-input" "$root/h3-input/build/kali-input"
mount -o remount,bind,ro "$root/h3-input/build/kali-input"
# Repository credentials/.git are not exposed inside the test root.
chroot "$root" /bin/bash <<'KALI'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y bubblewrap polkitd pkexec dbus-x11 gnome-keyring libsecret-1-0 libnss3 libatk1.0-0 libatk-bridge2.0-0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libxkbcommon0 libcairo2 libpango-1.0-0 libasound2t64 libgomp1
useradd -m -s /bin/bash h3check
tar -xzf /h3-input/build/kali-input/H3-Chat-*-linux-x64.tar.gz -C /home/h3check
chown -R h3check:h3check /home/h3check/H3-Chat
su --login --shell /bin/bash h3check <<'USER'
set -euo pipefail
dbus-run-session -- /bin/bash <<'SESSION'
set -euo pipefail
printf 'h3-disposable-ci-only\n' | gnome-keyring-daemon --unlock --components=secrets
/home/h3check/H3-Chat/runtime/python/bin/python3 -X utf8 /h3-input/scripts/check_linux.py /home/h3check/H3-Chat
SESSION
USER
KALI
HOST
