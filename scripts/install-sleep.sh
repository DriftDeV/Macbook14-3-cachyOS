#!/usr/bin/env bash
# Sospensione sul MacBookPro14,3: s2idle, hook Thunderbolt/Wi-Fi, NVMe senza D3cold,
# pm_async=0, ibernazione disattivata. Non serve riavviare.
#   sudo scripts/install-sleep.sh            installa
#   sudo scripts/install-sleep.sh --dry-run  mostra soltanto
#   sudo scripts/install-sleep.sh --undo     rimuove quanto installato
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=scripts/lib.sh
source "$SCRIPT_DIR/lib.sh"

HOOK=/usr/lib/systemd/system-sleep/macbookpro14-3-sleep.sh
SLEEPCONF=/etc/systemd/sleep.conf.d/10-macbookpro14-3.conf
UDEV=/etc/udev/rules.d/90-macbookpro14-3-nvme-no-d3cold.rules
TMPF=/etc/tmpfiles.d/macbookpro14-3-pm.conf
# Installati da versioni precedenti di questa repo.
OLD=(/usr/local/lib/macbookpro14-3/d3cold-nvme.sh /etc/systemd/system/macbookpro14-3-d3cold.service)

UNDO=0
for a in "$@"; do
    case "$a" in
        --dry-run) DRY_RUN=1 ;;
        --undo) UNDO=1 ;;
        *) die "Opzione sconosciuta: $a" ;;
    esac
done
need_root

if [ "$UNDO" = 1 ]; then
    run rm -fv "$HOOK" "$SLEEPCONF" "$UDEV" "$TMPF"
    run udevadm control --reload
    run sh -c 'echo 1 > /sys/power/pm_async'
    ok "Rimosso. D3cold dell'NVMe resta disattivato fino al prossimo riavvio."
    exit 0
fi

if [ "$(cat /sys/class/dmi/id/product_name 2>/dev/null)" != MacBookPro14,3 ] && [ "${FORCE:-0}" != 1 ]; then
    die "Questo hook è scritto per il MacBookPro14,3 (gli upstream port Thunderbolt sono cercati come 8086:1578)."
fi

for f in "${OLD[@]}"; do
    if [ -e "$f" ]; then
        log "Rimuovo $f (sostituito dalla regola udev)"
        [ "${f##*.}" = service ] && run systemctl disable "$(basename "$f")" || true
        run rm -f "$f"
    fi
done

log "Hook system-sleep (Thunderbolt remove/rescan, Wi-Fi)"
install_file 755 "$REPO_DIR/config/sleep/macbookpro14-3-sleep.sh" "$HOOK"

log "s2idle, ibernazione disattivata"
install_file 644 "$REPO_DIR/config/sleep/s2idle.conf" "$SLEEPCONF"

log "NVMe senza D3cold (per classe PCI)"
install_file 644 "$REPO_DIR/config/udev/90-macbookpro14-3-nvme-no-d3cold.rules" "$UDEV"
run udevadm control --reload
for d in /sys/bus/pci/devices/*; do
    [ "$(cat "$d/class")" = 0x010802 ] || continue
    run sh -c "echo 0 > '$d/d3cold_allowed'"
done

log "pm_async=0"
install_file 644 "$REPO_DIR/config/tmpfiles/macbookpro14-3-pm.conf" "$TMPF"
run systemd-tmpfiles --create "$TMPF"

for r in /usr/lib/udev/rules.d/39-usbmuxd.rules /etc/udev/rules.d/39-usbmuxd.rules; do
    if [ -f "$r" ] && grep -q '5ac/8600' "$r"; then
        warn "$r cita 05ac:8600: può spegnere il T1 (Touch Bar, webcam). Vedi docs/touchbar.md."
    fi
done

ok "Sospensione configurata. Prova: sudo scripts/sleep-test.sh platform, poi real."
