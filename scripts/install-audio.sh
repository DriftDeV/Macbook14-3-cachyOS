#!/usr/bin/env bash
# Installa via DKMS il driver Cirrus CS8409 per speaker, cuffie e microfoni
# (davidjo/snd_hda_macbookpro, fork dnlbtz branch offlineDkmsDeb, vedi config/sources.conf)
# con le patch di patches/audio/ (LLVM=1 per kernel clang).
# Per ogni kernel la build usa i file sound/hda di quella versione esatta, scaricati da kernel.org con
# scripts/kernel-src.sh (patch 0002, in cache per le ricompilazioni senza rete); senza rete ripiega sulla serie inclusa
# nel fork (kernel/7.3). Così DKMS lo ricompila da solo anche per i kernel futuri e per l'LTS.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=scripts/lib.sh
source "$SCRIPT_DIR/lib.sh"
# shellcheck source=config/sources.conf
source "$REPO_DIR/config/sources.conf"

[ "${1:-}" = "--dry-run" ] && DRY_RUN=1
need_root
for c in dkms git patch; do
    command -v "$c" >/dev/null && continue
    if [ "$DRY_RUN" = 1 ]; then warn "$c non installato."; else die "$c non installato."; fi
done
if ! has_cs8409 && [ "$FORCE" != 1 ]; then
    if [ "$DRY_RUN" = 1 ]; then warn "Codec CS8409 non rilevato."; else
        die "Codec CS8409 non rilevato (cerca 0x10138409 in /proc/asound/card*/codec#*). Usa FORCE=1 per ignorare."
    fi
fi

log "Clono $AUDIO_REPO (ref $AUDIO_REF)"
if [ "$DRY_RUN" = 1 ]; then
    echo "[dry-run] git clone + patch + dkms add/build/install snd_hda_macbookpro/0.1"
    exit 0
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
git clone --quiet "$AUDIO_REPO" "$WORK/src"
git -C "$WORK/src" checkout --quiet "$AUDIO_REF"
for p in "$REPO_DIR"/patches/audio/*.patch; do
    [ -e "$p" ] || continue
    log "Applico $(basename "$p")"
    git -C "$WORK/src" apply "$p" || die "Patch $(basename "$p") non applicabile su $AUDIO_REF."
done
install -m755 "$REPO_DIR/scripts/kernel-src.sh" "$WORK/src/kernel-src.sh"
rm -rf "$WORK/src/.git"

PKGNAME="$(sed -n 's/^PACKAGE_NAME="\(.*\)"$/\1/p' "$WORK/src/dkms.conf")"
PKGVER="$(sed -n 's/^PACKAGE_VERSION="\(.*\)"$/\1/p' "$WORK/src/dkms.conf")"
[ -n "$PKGNAME" ] && [ -n "$PKGVER" ] || die "dkms.conf del fork illeggibile."

# Rimuove installazioni precedenti (anche quella dello script upstream, che usa un link simbolico).
if dkms status "$PKGNAME/$PKGVER" 2>/dev/null | grep -q .; then
    log "Rimuovo la versione DKMS precedente $PKGNAME/$PKGVER"
    dkms remove "$PKGNAME/$PKGVER" --all >/dev/null 2>&1 || true
fi
rm -rf "/usr/src/$PKGNAME-$PKGVER"
cp -a "$WORK/src" "/usr/src/$PKGNAME-$PKGVER"
dkms add "$PKGNAME/$PKGVER"

BUILT=""
for k in /usr/lib/modules/*/; do
    kv="$(basename "$k")"
    [ -d "$k/build" ] || { warn "Header mancanti per $kv: salto."; continue; }
    log "dkms build/install per $kv"
    if dkms build "$PKGNAME/$PKGVER" -k "$kv"; then
        dkms install "$PKGNAME/$PKGVER" -k "$kv" --force
        BUILT="$BUILT $kv"
    else
        warn "Build DKMS fallita su $kv (speaker muti su quel kernel): /var/lib/dkms/$PKGNAME/$PKGVER/build/make.log"
    fi
done
[ -n "$BUILT" ] || die "Nessun kernel compatibile: il driver non è stato installato."
ok "Audio: $PKGNAME $PKGVER installato per:$BUILT. Riavvia per usarlo."
warn "Bug noto 14,3: se dopo un avvio il codec ha subsystem id 0x10138409 non esce audio. Vedi docs/audio.md."
