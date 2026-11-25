#!/usr/bin/env bash
# Impostazioni energetiche per alimentazione sul MacBookPro14,3 (/etc/macbookpro14-3/power.conf, chiavi AC_* e
# BATTERY_*): Radeon, turbo, frequenza massima, profilo, limite di potenza e tetto di temperatura della CPU, limite FPS
# (MangoHud). Predefinito: a batteria Radeon al minimo, CPU senza turbo, giochi a 60 FPS; con l'alimentatore piena
# potenza. Cambia da solo al collegamento/scollegamento, all'avvio e dopo lo sleep; si regola da MacBook Manager
# (schede CPU e GPU). Vedi docs/power.md.
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
LIMIT_BIN=/usr/local/lib/macbookpro14-3/cpu-limit.py
LIMIT_UNIT=/etc/systemd/system/macbookpro14-3-cpu-limit.service
MANGO=/etc/macbookpro14-3/mangohud.conf
ENVD=/etc/environment.d/90-macbookpro14-3-mangohud.conf
KWIN_DROPINS="/etc/systemd/user/plasma-kwin_wayland.service.d /etc/systemd/user/plasma-login-kwin_wayland.service.d"
NOMANGO=90-macbookpro14-3-no-mangohud.conf

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
    run systemctl disable --now macbookpro14-3-cpu-limit.service 2>/dev/null || true
    run rm -f "$BIN" "$RULE" "$UNIT" "$LIMIT_BIN" "$LIMIT_UNIT" "$MANGO" "$ENVD"
    for d in $KWIN_DROPINS; do run rm -f "$d/$NOMANGO" "$d/$NOMANGO.bak"; done
    run sh -c 'echo 100 > /sys/devices/system/cpu/intel_pstate/max_perf_pct'
    if [ -r /run/macbookpro14-3/power/pl1-default ]; then
        run sh -c 'cat /run/macbookpro14-3/power/pl1-default > /sys/class/powercap/intel-rapl:0/constraint_0_power_limit_uw'
    fi
    run systemctl daemon-reload
    run udevadm control --reload
    for d in /sys/bus/pci/drivers/amdgpu/0000:*; do
        [ "$(cat "$d/device" 2>/dev/null)" = 0x67ef ] || continue
        run sh -c "echo manual > $d/power_dpm_force_performance_level; echo 1 > $d/pp_power_profile_mode; echo auto > $d/power_dpm_force_performance_level"
    done
    run sh -c 'echo 0 > /sys/devices/system/cpu/intel_pstate/no_turbo'
    ok "Rimosso ($CONF lasciato al suo posto). Radeon su auto, turbo attivo, CPU senza limiti; il limite FPS sparisce dalla prossima sessione."
    exit 0
fi

install_file 755 "$REPO_DIR/config/power/power-source.sh" "$BIN"
if [ -e "$CONF" ]; then
    # Le chiavi già presenti restano come sono; quelle nuove vengono aggiunte con il valore predefinito.
    added=""
    while IFS= read -r line; do
        case "$line" in ''|\#*) continue ;; esac
        key="${line%%=*}"
        grep -q "^$key=" "$CONF" || { run sh -c "echo '$line' >> '$CONF'"; added="$added $key"; }
    done < "$REPO_DIR/config/power/power.conf"
    log "$CONF esiste già: lo lascio com'è${added:+ (aggiunte:$added)}."
else
    install_file 644 "$REPO_DIR/config/power/power.conf" "$CONF"
fi

log "Limite FPS a batteria: MangoHud (layer Vulkan, HUD nascosto)"
pk=(mangohud)
grep -q '^\[multilib\]' /etc/pacman.conf && pk+=(lib32-mangohud)   # giochi Vulkan a 32 bit
run pacman -S --needed --noconfirm "${pk[@]}"
[ -e "$MANGO" ] || run sh -c "printf 'no_display\nfps_limit=0\n' > '$MANGO'"
install_file 644 "$REPO_DIR/config/power/90-macbookpro14-3-mangohud.conf" "$ENVD"
# ...ma non dentro KWin (sessione e schermata di login): lì MangoHud lo faceva crollare
for d in $KWIN_DROPINS; do install_file 644 "$REPO_DIR/config/systemd/user/$NOMANGO" "$d/$NOMANGO"; done

log "Tetto di temperatura della CPU (servizio macbookpro14-3-cpu-limit)"
install_file 755 "$REPO_DIR/config/power/cpu-limit.py" "$LIMIT_BIN"
install_file 644 "$REPO_DIR/config/systemd/macbookpro14-3-cpu-limit.service" "$LIMIT_UNIT"
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
run systemctl enable macbookpro14-3-cpu-limit.service
run systemctl restart macbookpro14-3-cpu-limit.service
run "$BIN"
ok "Impostazioni energetiche attive. Controllo: journalctl -t macbookpro14-3-power"
echo "Il limite FPS vale dalla prossima sessione (esci e rientra): MangoHud si carica con l'ambiente del login."
