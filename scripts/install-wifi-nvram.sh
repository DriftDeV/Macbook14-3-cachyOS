#!/usr/bin/env bash
# Installa il file NVRAM del BCM43602 per il MacBookPro14,3.
# Senza questo file il Wi-Fi funziona solo a 2,4 GHz con cadute.
#
# Il file NON è incluso nella repo (licenza poco chiara). Estrailo da macOS /
# Boot Camp, oppure usa uno già in tuo possesso:
#   sudo scripts/install-wifi-nvram.sh --file /percorso/brcmfmac43602-pcie.txt
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib.sh
source "$SCRIPT_DIR/lib.sh"

FILE=""
while [ $# -gt 0 ]; do
    case "$1" in
        --file) FILE="${2:-}"; shift 2 ;;
        --dry-run) DRY_RUN=1; shift ;;
        *) die "Argomento sconosciuto: $1" ;;
    esac
done
[ -n "$FILE" ] || die "Uso: $0 --file <nvram.txt> [--dry-run]"
[ -r "$FILE" ] || die "File non leggibile: $FILE"
need_root

DST="/usr/lib/firmware/brcm/brcmfmac43602-pcie.Apple Inc.-MacBookPro14,3.txt"
install_file 644 "$FILE" "$DST"
if [ "$DRY_RUN" != 1 ]; then
    modprobe -r brcmfmac_wcc 2>/dev/null || true
    modprobe -r brcmfmac 2>/dev/null || true
    modprobe brcmfmac
fi
ok "NVRAM installato. Verifica con: journalctl -k | grep brcmfmac"
warn "Se vedi crash del firmware, prova l'opzione in config/modprobe.d/brcmfmac.conf.example"
