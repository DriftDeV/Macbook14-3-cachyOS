#!/usr/bin/env bash
# Compila e installa via DKMS i moduli Touch Bar T1 (apple-ibridge, apple-ib-tb, apple-ib-als).
# La sorgente è scelta in config/sources.conf; le patch in patches/touchbar/ vengono
# applicate sopra (port a Linux 7.3, LLVM=1 per kernel clang). Se la build fallisce lo script
# esce con errore SENZA toccare il resto del sistema: la Touch Bar è la parte più fragile.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=scripts/lib.sh
source "$SCRIPT_DIR/lib.sh"
# shellcheck source=config/sources.conf
source "$REPO_DIR/config/sources.conf"

[ "${1:-}" = "--dry-run" ] && DRY_RUN=1
need_root
for c in dkms git; do
    command -v "$c" >/dev/null && continue
    if [ "$DRY_RUN" = 1 ]; then warn "$c non installato (serve: pacman -S $c)."; else die "$c non installato."; fi
done

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

log "Clono $TOUCHBAR_REPO ${TOUCHBAR_REF:+(ref $TOUCHBAR_REF)}"
if [ "$DRY_RUN" = 1 ]; then
    echo "[dry-run] git clone $TOUCHBAR_REPO ; dkms add/build/install"
    exit 0
fi
git clone --quiet "$TOUCHBAR_REPO" "$WORK/src"
[ -z "$TOUCHBAR_REF" ] || git -C "$WORK/src" checkout --quiet "$TOUCHBAR_REF"
SHA="$(git -C "$WORK/src" rev-parse --short HEAD)"
VERSION="git.$SHA"
DEST="/usr/src/apple-ibridge-$VERSION"

for p in "$REPO_DIR"/patches/touchbar/*.patch; do
    [ -e "$p" ] || continue
    log "Applico $(basename "$p")"
    git -C "$WORK/src" apply "$p" || die "Patch $(basename "$p") non applicabile su $SHA."
done

# Rimuove vecchie versioni (il nome DKMS dipende dal fork: apple-ibridge o appleibridge).
dkms status 2>/dev/null | awk -F'[,/: ]+' '$1=="apple-ibridge"||$1=="appleibridge"{print $1" "$2}' | sort -u |
while read -r name old; do
    log "Rimuovo versione DKMS precedente: $name/$old"
    dkms remove "$name/$old" --all >/dev/null 2>&1 || true
    rm -rf "/usr/src/$name-$old"
done

# Regola udev del fork: toglie a hid-sensor-hub l'interfaccia HID della Touch Bar
# (sul T1 porta anche il sensore di luce, e senza questa regola la barra resta spenta).
if [ -f "$WORK/src/udev/90-apple-ibridge-t1.rules" ]; then
    install_file 644 "$WORK/src/udev/90-apple-ibridge-t1.rules" /etc/udev/rules.d/90-apple-ibridge-t1.rules
    udevadm control --reload || true
fi

rm -rf "$DEST"
mkdir -p "$DEST"
rm -rf "$WORK/src/.git"
cp -a "$WORK/src/." "$DEST/"

if [ -f "$DEST/dkms.conf" ]; then
    log "Uso il dkms.conf fornito dal fork."
else
    warn "Il fork non ha dkms.conf: uso quello della repo (non verificato)."
    sed "s/@VERSION@/$VERSION/" "$REPO_DIR/dkms/apple-ibridge/dkms.conf" > "$DEST/dkms.conf"
fi
[ -f "$DEST/Makefile" ] || die "Nessun Makefile in $DEST: la struttura del fork non è quella attesa."

PKGVER="$(awk -F'"' '/^PACKAGE_VERSION=/{print $2; exit}' "$DEST/dkms.conf")"
PKGNAME="$(awk -F'"' '/^PACKAGE_NAME=/{print $2; exit}' "$DEST/dkms.conf")"
[ -n "$PKGVER" ] && [ -n "$PKGNAME" ] || die "dkms.conf illeggibile."
# DKMS cerca /usr/src/<nome>-<versione>.
if [ "$DEST" != "/usr/src/$PKGNAME-$PKGVER" ]; then
    rm -rf "/usr/src/$PKGNAME-$PKGVER"
    mv "$DEST" "/usr/src/$PKGNAME-$PKGVER"
fi

dkms add "$PKGNAME/$PKGVER"
for k in /usr/lib/modules/*/; do
    kv="$(basename "$k")"
    [ -d "$k/build" ] || { warn "Header mancanti per $kv: salto."; continue; }
    log "dkms build/install per $kv"
    dkms build "$PKGNAME/$PKGVER" -k "$kv" || die "Build DKMS fallita su $kv. Vedi /var/lib/dkms/$PKGNAME/$PKGVER/build/make.log"
    dkms install "$PKGNAME/$PKGVER" -k "$kv" --force
done

# Caricamento automatico solo se i moduli esistono davvero.
: > /etc/modules-load.d/apple-ibridge.conf
for m in apple-ibridge apple-ib-tb apple-ib-als; do
    if modinfo "$m" >/dev/null 2>&1; then echo "$m" >> /etc/modules-load.d/apple-ibridge.conf; fi
done
# usbmuxd 1.1.1 mette il T1 in configurazione 0 (niente Touch Bar, ALS, webcam).
for r in /usr/lib/udev/rules.d/39-usbmuxd.rules /etc/udev/rules.d/39-usbmuxd.rules; do
    if [ -f "$r" ] && grep -q '5ac/8600' "$r"; then
        warn "$r cita 05ac:8600: può spegnere il T1. Vedi docs (Touch Bar, usbmuxd)."
    fi
done
ok "Touch Bar: moduli installati ($PKGNAME $PKGVER). Riavvia per caricarli."
warn "Se la barra non si accende: vedi scripts/t1-reenumerate.sh e docs/research-report.md (sezione Touch Bar)."
