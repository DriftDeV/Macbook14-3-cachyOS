#!/usr/bin/env bash
# CI: compila con DKMS tutti i driver della repo contro ogni kernel con gli header installati (in un container Arch),
# preparando i sorgenti come fanno gli script di installazione: stesso commit fissato in config/sources.conf, stesse
# patch, stessi file della repo. Non installa né carica niente. Esce con errore se un driver non compila.
#   .github/scripts/build-drivers.sh            (da root, nella radice della repo)
set -uo pipefail
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=config/sources.conf
source "$REPO_DIR/config/sources.conf"
WORK="$(mktemp -d)"
FAILED=() OKS=()

kernels=()
for k in /usr/lib/modules/*/; do [ -d "$k/build" ] && kernels+=("$(basename "$k")"); done
[ "${#kernels[@]}" -gt 0 ] || { echo "Nessun header del kernel installato." >&2; exit 1; }
echo "Kernel: ${kernels[*]}"

# add_build <cartella sorgente con dkms.conf>: la copia in /usr/src/<nome>-<versione>, dkms add e build per ogni kernel.
add_build() {
    local src="$1" name ver kv
    name="$(sed -n 's/^PACKAGE_NAME="\(.*\)"$/\1/p' "$src/dkms.conf")"
    ver="$(sed -n 's/^PACKAGE_VERSION="\(.*\)"$/\1/p' "$src/dkms.conf")"
    [ -n "$name" ] && [ -n "$ver" ] || { FAILED+=("$src: dkms.conf illeggibile"); return; }
    rm -rf "/usr/src/$name-$ver"
    cp -a "$src" "/usr/src/$name-$ver"
    dkms add "$name/$ver" >/dev/null || { FAILED+=("$name: dkms add"); return; }
    for kv in "${kernels[@]}"; do
        echo "::group::$name/$ver per $kv"
        if dkms build "$name/$ver" -k "$kv"; then
            OKS+=("$name $kv")
        else
            cat "/var/lib/dkms/$name/$ver/build/make.log" 2>/dev/null | tail -60
            FAILED+=("$name $kv")
        fi
        echo "::endgroup::"
    done
}

# Touch Bar, modalità tastiera (apple-ibridge): fork + patches/touchbar (come scripts/install-touchbar.sh).
git clone --quiet "$TOUCHBAR_REPO" "$WORK/touchbar" && git -C "$WORK/touchbar" checkout --quiet "$TOUCHBAR_REF"
for p in "$REPO_DIR"/patches/touchbar/*.patch; do
    git -C "$WORK/touchbar" apply "$p" || FAILED+=("patch $(basename "$p")")
done
rm -rf "$WORK/touchbar/.git"
[ -f "$WORK/touchbar/dkms.conf" ] || sed "s/@VERSION@/ci/" "$REPO_DIR/dkms/apple-ibridge/dkms.conf" > "$WORK/touchbar/dkms.conf"
add_build "$WORK/touchbar"

# Audio CS8409: fork + patches/audio (come scripts/install-audio.sh).
git clone --quiet "$AUDIO_REPO" "$WORK/audio" && git -C "$WORK/audio" checkout --quiet "$AUDIO_REF"
for p in "$REPO_DIR"/patches/audio/*.patch; do
    git -C "$WORK/audio" apply "$p" || FAILED+=("patch $(basename "$p")")
done
install -m755 "$REPO_DIR/scripts/kernel-src.sh" "$WORK/audio/kernel-src.sh"
rm -rf "$WORK/audio/.git"
add_build "$WORK/audio"

# Modalità display: display, webcam, rete per Touch ID (come scripts/install-touchbar-display.sh).
for p in t1bridge-appletbdrm t1bridge-uvc t1bridge-ncm; do
    cp -a "$REPO_DIR/dkms/$p" "$WORK/$p"
    install -m755 "$REPO_DIR/scripts/kernel-src.sh" "$WORK/$p/kernel-src.sh"
    add_build "$WORK/$p"
done

echo
echo "Compilati: ${#OKS[@]}"; printf '  %s\n' "${OKS[@]}"
if [ "${#FAILED[@]}" -gt 0 ]; then
    echo "NON riusciti: ${#FAILED[@]}"; printf '  %s\n' "${FAILED[@]}"
    exit 1
fi
