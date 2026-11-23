#!/usr/bin/env bash
# Bluetooth del MacBookPro14,3 (Broadcom su UART): audio delle chiamate (profilo headset HSP/HFP)
# instradato via HCI, così funziona con il codec CVSD. Vedi docs/audio.md.
#   sudo scripts/install-bt.sh            installa e applica subito
#   sudo scripts/install-bt.sh --dry-run  mostra soltanto
#   sudo scripts/install-bt.sh --undo     rimuove (al prossimo reset del controller torna il default)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=scripts/lib.sh
source "$SCRIPT_DIR/lib.sh"

BIN=/usr/local/lib/macbookpro14-3/bt-sco-route.py
UNIT=/etc/systemd/system/macbookpro14-3-bt-sco.service
WPCONF=/etc/wireplumber/wireplumber.conf.d/51-macbookpro14-3-bluetooth.conf
HOOK=/usr/lib/systemd/system-sleep/macbookpro14-3-sleep.sh

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
    run systemctl disable macbookpro14-3-bt-sco.service 2>/dev/null || true
    run rm -f "$BIN" "$UNIT" "$WPCONF"
    run systemctl daemon-reload
    ok "Rimosso: dal prossimo riavvio del Bluetooth l'audio SCO torna sul PCM del chip (profilo headset muto)."
    exit 0
fi

grep -qs BCM2E7C /sys/class/bluetooth/hci0/device/modalias || [ "${FORCE:-0}" = 1 ] \
    || die "Bluetooth Broadcom UART (BCM2E7C) non trovato su hci0."
run install -Dm755 "$REPO_DIR/scripts/bt-sco-route.py" "$BIN"
install_file 644 "$REPO_DIR/config/systemd/macbookpro14-3-bt-sco.service" "$UNIT"
# mSBC disattivato in WirePlumber: il profilo headset usa CVSD (unico che funziona). Vale dal
# prossimo riavvio di WirePlumber (systemctl --user restart wireplumber, o nuovo login).
install_file 644 "$REPO_DIR/config/wireplumber/51-macbookpro14-3-bluetooth.conf" "$WPCONF"
if [ -e "$HOOK" ]; then   # l'hook di sleep riapplica il comando dopo il risveglio
    run install -Dm755 "$REPO_DIR/config/sleep/macbookpro14-3-sleep.sh" "$HOOK"   # niente .bak: verrebbe eseguito
fi
run systemctl daemon-reload
run systemctl enable macbookpro14-3-bt-sco.service
run python3 -I "$BIN" hci0
ok "Profilo headset con CVSD pronto (mSBC disattivato). Riavvia WirePlumber da utente: systemctl --user restart wireplumber"
