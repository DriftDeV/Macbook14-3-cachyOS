#!/usr/bin/env bash
# Backup dell'ESP Apple. Contiene il firmware del chip T1
# (EFI/APPLE/EMBEDDEDOS/combined.memboot): se viene cancellato, Touch Bar,
# webcam e sensore di luce smettono di funzionare tutti insieme.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib.sh
source "$SCRIPT_DIR/lib.sh"

DEST="${1:-/var/backups/macbookpro14-3}"
need_root

# Individua l'ESP di Apple: tra le partizioni EFI (tipo GPT c12a7328-...) quella con EFI/APPLE.
# Sui Mac con Linux installato accanto a macOS ce ne possono essere più d'una (es. una per GRUB).
ESP=""
PROBE="$(mktemp -d)"
for p in $(lsblk -rno PATH,PARTTYPE 2>/dev/null | awk 'tolower($2)=="c12a7328-f81f-11d2-ba4b-00a0c93ec93b"{print $1}'); do
    [ -n "$ESP" ] || ESP="$p"                       # ripiego: la prima
    if mount -o ro "$p" "$PROBE" 2>/dev/null; then
        found=0; [ -d "$PROBE/EFI/APPLE" ] && found=1
        umount "$PROBE"
        if [ "$found" = 1 ]; then ESP="$p"; break; fi
    elif findmnt -rno TARGET "$p" >/dev/null 2>&1 && [ -d "$(findmnt -rno TARGET "$p" | head -1)/EFI/APPLE" ]; then
        ESP="$p"; break                             # già montata altrove
    fi
done
rmdir "$PROBE" 2>/dev/null || true
[ -n "$ESP" ] || die "ESP non trovata."
log "ESP: $ESP"

run mkdir -p "$DEST"
STAMP="$(date +%Y%m%d-%H%M%S)"
run dd if="$ESP" of="$DEST/esp-$STAMP.img" bs=1M status=none
if [ "$DRY_RUN" != 1 ]; then
    sfdisk -d "$(lsblk -no PKNAME "$ESP" | head -1 | sed 's|^|/dev/|')" > "$DEST/partition-table-$STAMP.txt" 2>/dev/null || true
    sha256sum "$DEST/esp-$STAMP.img" > "$DEST/esp-$STAMP.img.sha256"
fi

# Copia anche il solo firmware T1 se presente (file piccolo, facile da ripristinare).
TMP="$(mktemp -d)"
trap 'umount "$TMP" 2>/dev/null || true; rmdir "$TMP" 2>/dev/null || true' EXIT
if [ "$DRY_RUN" != 1 ] && mount -o ro "$ESP" "$TMP" 2>/dev/null; then
    if [ -d "$TMP/EFI/APPLE" ]; then
        cp -a "$TMP/EFI/APPLE" "$DEST/EFI-APPLE-$STAMP"
        ok "Firmware Apple/T1 copiato in $DEST/EFI-APPLE-$STAMP"
    else
        warn "EFI/APPLE non presente su questa ESP."
    fi
fi
ok "Backup in $DEST"
