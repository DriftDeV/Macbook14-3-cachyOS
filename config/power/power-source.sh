#!/bin/bash
# Applica le impostazioni energetiche in base all'alimentazione (alimentatore o batteria).
# Lanciato dalla regola udev al collegamento/scollegamento, all'avvio dal servizio
# macbookpro14-3-power-source e dopo lo sleep dall'hook macbookpro14-3-sleep.sh.
CONF=/etc/macbookpro14-3/power.conf
BATTERY_RADEON_SAVE=1
BATTERY_NO_TURBO=1
# shellcheck source=/dev/null
[ -r "$CONF" ] && . "$CONF"

log() { echo "$*" | systemd-cat -t macbookpro14-3-power; }
wr() { echo "$2" > "$1" 2>/dev/null || log "scrittura di '$2' in $1 fallita"; }

ac=1
for s in /sys/class/power_supply/*; do
    [ "$(cat "$s/type" 2>/dev/null)" = Mains ] && ac="$(cat "$s/online")" && break
done

# Radeon Pro 555/560 (Baffin, 1002:67ef), cercata per ID e non per numero di card.
gpu=""
for d in /sys/bus/pci/drivers/amdgpu/0000:*; do
    [ "$(cat "$d/device" 2>/dev/null)" = 0x67ef ] && gpu="$d" && break
done

pstate=/sys/devices/system/cpu/intel_pstate
if [ "$ac" = 1 ]; then
    if [ -n "$gpu" ]; then
        # Il profilo si cambia solo in modalità manual; poi si torna ad auto.
        wr "$gpu/power_dpm_force_performance_level" manual
        wr "$gpu/pp_power_profile_mode" 1           # 3D_FULL_SCREEN
        wr "$gpu/power_dpm_force_performance_level" auto
    fi
    [ -w "$pstate/no_turbo" ] && wr "$pstate/no_turbo" 0
    log "alimentatore: Radeon auto, turbo CPU attivo"
else
    if [ -n "$gpu" ] && [ "$BATTERY_RADEON_SAVE" = 1 ]; then
        wr "$gpu/power_dpm_force_performance_level" manual
        wr "$gpu/pp_power_profile_mode" 2           # POWER_SAVING
        # PCIe al minimo (2,5 GT/s x8): tentativo singolo. Sul 14,3 di solito resta a 8 GT/s
        # e il risparmio misurato (-1,5 W) viene da manual + POWER_SAVING (docs/power.md).
        wr "$gpu/pp_dpm_pcie" 0
    fi
    [ -w "$pstate/no_turbo" ] && [ "$BATTERY_NO_TURBO" = 1 ] && wr "$pstate/no_turbo" 1
    log "batteria: Radeon risparmio=$BATTERY_RADEON_SAVE, CPU senza turbo=$BATTERY_NO_TURBO"
fi
exit 0
