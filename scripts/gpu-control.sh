#!/usr/bin/env bash
# Controlli GPU del MacBookPro14,3 per MacBook Manager (scheda GPU). Solo comandi fissi, nessun valore libero.
# Installato da scripts/install-manager.sh in /usr/local/lib/macbookpro14-3/gpu-control.sh; lo usa l'helper di root.
#   gpu-control.sh display intel|radeon   GPU dello schermo al PROSSIMO avvio (variabile EFI gpu-power-prefs, come
#                                          gpu-switch). Basta da sola, anche senza OpenCore (provato il
#                                          26/11/2026, docs/gpu.md).
#   gpu-control.sh radeon auto|game|save|low|high
#       auto: livello automatico (profilo predefinito)   game: automatico + profilo 3D_FULL_SCREEN (come con l'alimentatore)
#       save: manual + POWER_SAVING (come a batteria)     low/high: clock fissi al minimo / al massimo
#     Vale fino al prossimo cambio di alimentazione: power-source.sh riapplica le regole di /etc/macbookpro14-3/power.conf.
#   gpu-control.sh status
set -euo pipefail

VAR=/sys/firmware/efi/efivars/gpu-power-prefs-fa4ce28d-b62f-4c99-9cc3-6815686e30f9

radeon_dir() {
    local d
    for d in /sys/bus/pci/drivers/amdgpu/0000:*; do
        [ -e "$d/power_dpm_force_performance_level" ] && { echo "$d"; return 0; }
    done
    echo "Radeon (amdgpu) non trovata" >&2
    return 1
}

wr() { echo "$2" > "$1" || { echo "scrittura di '$2' in $1 fallita" >&2; return 1; }; }

case "${1:-} ${2:-}" in
    "display intel"|"display radeon")
        [ "$(id -u)" = 0 ] || { echo "Serve root." >&2; exit 1; }
        chattr -i "$VAR" 2>/dev/null || true
        tmp="$(mktemp)"
        if [ "$2" = intel ]; then
            printf '\x07\x00\x00\x00\x01\x00\x00\x00' > "$tmp"
        else
            printf '\x07\x00\x00\x00\x00\x00\x00\x00' > "$tmp"
        fi
        dd if="$tmp" of="$VAR" bs=8 count=1 status=none
        rm -f "$tmp"
        echo "GPU dello schermo al prossimo avvio: $2 (gpu-power-prefs = $(od -An -tx1 "$VAR" | awk '{print $5}'))."
        echo "Riavvia per applicarla." ;;
    "radeon auto"|"radeon game"|"radeon save"|"radeon low"|"radeon high")
        [ "$(id -u)" = 0 ] || { echo "Serve root." >&2; exit 1; }
        g="$(radeon_dir)"
        case "$2" in
            auto) wr "$g/power_dpm_force_performance_level" auto ;;
            game) wr "$g/power_dpm_force_performance_level" manual
                  wr "$g/pp_power_profile_mode" 1
                  wr "$g/power_dpm_force_performance_level" auto ;;
            save) wr "$g/power_dpm_force_performance_level" manual
                  wr "$g/pp_power_profile_mode" 2 ;;
            low|high) wr "$g/power_dpm_force_performance_level" "$2" ;;
        esac
        echo "Radeon: livello $(cat "$g/power_dpm_force_performance_level"), profilo $(awk '/\*/{print $2}' "$g/pp_power_profile_mode" | tr -d ':*')."
        echo "Vale fino al prossimo cambio di alimentazione (poi tornano le regole di power.conf)." ;;
    "status "*)
        echo "gpu-power-prefs: $(od -An -tx1 "$VAR" 2>/dev/null | awk '{print $5}')"
        g="$(radeon_dir)" && echo "Radeon: $(cat "$g/power_dpm_force_performance_level"), $(awk '/\*/{print $2}' "$g/pp_power_profile_mode" | tr -d ':*')" ;;
    *)
        echo "Uso: gpu-control.sh display intel|radeon | radeon auto|game|save|low|high | status" >&2
        exit 2 ;;
esac
