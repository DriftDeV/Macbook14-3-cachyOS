#!/usr/bin/env bash
# Impostazioni energetiche per alimentazione sul MacBookPro14,3: a batteria Radeon in risparmio
# (POWER_SAVING + PCIe 2,5 GT/s) e CPU senza turbo; con l'alimentatore piena potenza.
# Cambia da solo al collegamento/scollegamento, all'avvio e dopo lo sleep. Vedi docs/power.md.
#   sudo scripts/install-power.sh            installa e applica subito
#   sudo scripts/install-power.sh --dry-run  mostra soltanto
#   sudo scripts/install-power.sh --undo     rimuove e torna ai valori di default
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=scripts/lib.sh
source "$SCRIPT_DIR/lib.sh"

BIN=/usr/local/lib/macbookpro14-3/power-source.sh
CONF=/etc/macbookpro14-3/power.conf
RULE=/etc/udev/rules.d/91-macbookpro14-3-power-source.rules
UNIT=/etc/systemd/system/macbookpro14-3-power-source.service

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
    run systemctl disable macbookpro14-3-power-source.service 2>/dev/null || true
    run rm -f "$BIN" "$RULE" "$UNIT"
    run systemctl daemon-reload
    run udevadm control --reload
    for d in /sys/bus/pci/drivers/amdgpu/0000:*; do
        [ "$(cat "$d/device" 2>/dev/null)" = 0x67ef ] || continue
        run sh -c "echo manual > $d/power_dpm_force_performance_level; echo 1 > $d/pp_power_profile_mode; echo auto > $d/power_dpm_force_performance_level"
    done
    run sh -c 'echo 0 > /sys/devices/system/cpu/intel_pstate/no_turbo'
    ok "Rimosso ($CONF lasciato al suo posto). Radeon su auto, turbo attivo."
    exit 0
fi

install_file 755 "$REPO_DIR/config/power/power-source.sh" "$BIN"
if [ -e "$CONF" ]; then
    log "$CONF esiste già: lo lascio com'è."
else
    install_file 644 "$REPO_DIR/config/power/power.conf" "$CONF"
fi
install_file 644 "$REPO_DIR/config/udev/91-macbookpro14-3-power-source.rules" "$RULE"
HOOK=/usr/lib/systemd/system-sleep/macbookpro14-3-sleep.sh
if [ -e "$HOOK" ]; then   # versione dell'hook che riapplica queste impostazioni dopo lo sleep
    # Niente .bak qui: systemd-sleep eseguirebbe anche la copia.
    run install -Dm755 "$REPO_DIR/config/sleep/macbookpro14-3-sleep.sh" "$HOOK"
fi
install_file 644 "$REPO_DIR/config/systemd/macbookpro14-3-power-source.service" "$UNIT"
run udevadm control --reload
run systemctl daemon-reload
run systemctl enable macbookpro14-3-power-source.service
run "$BIN"
ok "Impostazioni energetiche attive. Controllo: journalctl -t macbookpro14-3-power"
