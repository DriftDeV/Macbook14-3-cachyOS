#!/bin/bash
# shellcheck disable=SC2034  # i valori AC_*/BATTERY_* si leggono per nome con get()
# Applica le impostazioni energetiche in base all'alimentazione (alimentatore o batteria), da
# /etc/macbookpro14-3/power.conf (chiavi AC_* e BATTERY_*; le sceglie MacBook Manager, schede CPU e GPU).
# Lanciato dalla regola udev al collegamento/scollegamento, all'avvio dal servizio macbookpro14-3-power-source,
# dopo lo sleep dall'hook macbookpro14-3-sleep.sh e dalle azioni del manager.
# Il limite di temperatura della CPU lo applica il servizio macbookpro14-3-cpu-limit (cpu-limit.py), che legge
# lo stesso file ogni 2 secondi.
CONF=/etc/macbookpro14-3/power.conf
MANGO=/etc/macbookpro14-3/mangohud.conf
STATE=/run/macbookpro14-3/power

# Valori predefiniti (chiave assente nel file); si leggono per nome con get(), da qui il disable SC2034.
AC_NO_TURBO=0
AC_CPU_MAX_PCT=100
AC_CPU_PROFILE=keep
AC_CPU_POWER_W=0
AC_FPS_LIMIT=0
BATTERY_NO_TURBO=1
BATTERY_CPU_MAX_PCT=100
BATTERY_CPU_PROFILE=keep
BATTERY_CPU_POWER_W=0
BATTERY_FPS_LIMIT=60
BATTERY_RADEON_SAVE=1
BATTERY_RADEON_MODE=""
# shellcheck source=/dev/null
[ -r "$CONF" ] && . "$CONF"
# Compatibilità: prima c'era solo BATTERY_RADEON_SAVE (1 = risparmio, 0 = automatica).
if [ -z "$BATTERY_RADEON_MODE" ]; then
    if [ "$BATTERY_RADEON_SAVE" = 1 ]; then BATTERY_RADEON_MODE=save; else BATTERY_RADEON_MODE=auto; fi
fi

log() { echo "$*" | systemd-cat -t macbookpro14-3-power; }
wr() { echo "$2" > "$1" 2>/dev/null || log "scrittura di '$2' in $1 fallita"; }
num() { case "$1" in ''|*[!0-9]*) echo "$2" ;; *) echo "$1" ;; esac; }

ac=1
for s in /sys/class/power_supply/*; do
    [ "$(cat "$s/type" 2>/dev/null)" = Mains ] && ac="$(cat "$s/online")" && break
done
if [ "$ac" = 1 ]; then side=AC; else side=BATTERY; fi
get() { local v="${side}_$1"; echo "${!v}"; }
mkdir -p "$STATE"
echo "$side" > "$STATE/source"

# --- Radeon Pro 555/560 (Baffin, 1002:67ef), cercata per ID e non per numero di card ---------------------
gpu=""
for d in /sys/bus/pci/drivers/amdgpu/0000:*; do
    [ "$(cat "$d/device" 2>/dev/null)" = 0x67ef ] && gpu="$d" && break
done
radeon_game() {   # automatica con il profilo 3D_FULL_SCREEN (il profilo si cambia solo in manual)
    wr "$gpu/power_dpm_force_performance_level" manual
    wr "$gpu/pp_power_profile_mode" 1
    wr "$gpu/power_dpm_force_performance_level" auto
}
rmode=game
[ "$side" = BATTERY ] && rmode="$BATTERY_RADEON_MODE"
if [ -n "$gpu" ]; then
    case "$rmode" in
        low)  # clock al minimo (sclk 214 MHz, mclk 300 MHz): il consumo più basso anche nei giochi
            wr "$gpu/power_dpm_force_performance_level" low ;;
        save) # POWER_SAVING + PCIe al minimo (tentativo: sul 14,3 di solito resta a 8 GT/s; docs/power.md)
            wr "$gpu/power_dpm_force_performance_level" manual
            wr "$gpu/pp_power_profile_mode" 2
            wr "$gpu/pp_dpm_pcie" 0 ;;
        *) radeon_game ;;
    esac
fi

# --- CPU ------------------------------------------------------------------------------------------------
pstate=/sys/devices/system/cpu/intel_pstate
turbo_off="$(num "$(get NO_TURBO)" 0)"
[ -w "$pstate/no_turbo" ] && wr "$pstate/no_turbo" "$turbo_off"
maxpct="$(num "$(get CPU_MAX_PCT)" 100)"
[ "$maxpct" -ge 30 ] && [ "$maxpct" -le 100 ] || maxpct=100
[ -w "$pstate/max_perf_pct" ] && wr "$pstate/max_perf_pct" "$maxpct"   # cpu-limit.py lo abbassa se scalda

profile="$(get CPU_PROFILE)"
case "$profile" in
    performance|balanced|power-saver)
        command -v powerprofilesctl >/dev/null && { powerprofilesctl set "$profile" 2>/dev/null \
            || log "powerprofilesctl set $profile fallito"; } ;;
esac

# Limite di potenza a lungo termine (RAPL PL1). 0 = valore del firmware, salvato al primo uso in questo avvio.
rapl=/sys/class/powercap/intel-rapl:0
watts="$(num "$(get CPU_POWER_W)" 0)"
if [ -w "$rapl/constraint_0_power_limit_uw" ] && [ "$(cat "$rapl/constraint_0_name" 2>/dev/null)" = long_term ]; then
    [ -e "$STATE/pl1-default" ] || cat "$rapl/constraint_0_power_limit_uw" > "$STATE/pl1-default"
    if [ "$watts" -ge 10 ] && [ "$watts" -le 100 ]; then
        wr "$rapl/constraint_0_power_limit_uw" "$((watts * 1000000))"
    else
        wr "$rapl/constraint_0_power_limit_uw" "$(cat "$STATE/pl1-default")"
        watts=0
    fi
fi

# --- Limite FPS (MangoHud, /etc/environment.d/90-macbookpro14-3-mangohud.conf): i giochi Vulkan già aperti
# rileggono il file da soli; 0 = nessun limite -------------------------------------------------------------
fps="$(num "$(get FPS_LIMIT)" 0)"
if [ -d "$(dirname "$MANGO")" ]; then
    printf '# Scritto da power-source.sh (%s): limite FPS per MangoHud, cambia con l alimentazione.\nno_display\nfps_limit=%s\n' \
        "$side" "$fps" > "$MANGO.tmp" && chmod 644 "$MANGO.tmp" && mv -f "$MANGO.tmp" "$MANGO"
fi

log "$( [ "$side" = AC ] && echo alimentatore || echo batteria ): Radeon $rmode, turbo $([ "$turbo_off" = 1 ] && echo spento || echo attivo), CPU max $maxpct %, profilo $profile, limite $([ "$watts" = 0 ] && echo firmware || echo "$watts W"), FPS $([ "$fps" = 0 ] && echo liberi || echo "max $fps")"
exit 0
