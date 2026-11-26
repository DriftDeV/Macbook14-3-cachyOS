#!/usr/bin/env bash
# Variabili NVRAM utili del MacBookPro14,3 per MacBook Manager (scheda NVRAM). Solo comandi fissi, nessun valore libero:
# lo usa l'helper di root (azioni nvram-* di actions.py). Installato da scripts/install-manager.sh in
# /usr/local/lib/macbookpro14-3/nvram-control.sh.
#   nvram-control.sh chime on|off           suono di avvio (StartupMute, GUID Apple 7C436110: 00 = suona, 01 = muto)
#   nvram-control.sh autoboot on|off        accensione aprendo il coperchio o collegando l'alimentatore (AutoBoot:
#                                           00 = no, 03 = sì, il valore predefinito; [NV] sul 14,3)
#   nvram-control.sh boot default|next opencore|linux
#                                           disco/voce di avvio: "default" la mette prima in BootOrder, "next" solo per il
#                                           prossimo avvio (BootNext). linux = Limine, GRUB o un'altra voce Linux.
#   nvram-control.sh status
# La GPU dello schermo (gpu-power-prefs) resta in gpu-control.sh. Ogni scrittura conserva gli attributi della variabile.
set -euo pipefail

APPLE=7c436110-ab2a-4bbb-a880-fe41995c9f82
VARS=/sys/firmware/efi/efivars

[ -d "$VARS" ] || { echo "Variabili EFI non disponibili (avvio non UEFI?)." >&2; exit 1; }

# setvar NOME VALORE_HEX (un byte): scrive attributi + valore, conservando gli attributi se la variabile esiste.
setvar() {
    local f="$VARS/$1-$APPLE" attr tmp
    if [ -e "$f" ]; then attr="$(od -An -tx1 -N4 "$f" | tr -d ' \n')"; else attr=07000000; fi
    chattr -i "$f" 2>/dev/null || true
    tmp="$(mktemp)"
    # shellcheck disable=SC2059  # i byte vengono da valori fissi qui sopra
    printf "$(echo "$attr$2" | sed 's/../\\x&/g')" > "$tmp"
    dd if="$tmp" of="$f" bs=$(( ${#attr} / 2 + ${#2} / 2 )) count=1 status=none
    rm -f "$tmp"
    echo "$1 = $(od -An -tx1 -j4 "$f" | tr -d ' \n')"
}

getvar() {   # valore (hex, senza attributi) o "assente"
    local f="$VARS/$1-$APPLE"
    if [ -e "$f" ]; then od -An -tx1 -j4 "$f" | tr -d ' \n'; else echo assente; fi
}

# Numero (4 cifre) della prima voce di avvio il cui nome corrisponde: opencore oppure linux.
entry() {
    local re
    case "$1" in
        opencore) re='OpenCore' ;;
        linux) re='Limine|GRUB|CachyOS|Omarchy|Arch|Linux Boot Manager|rEFInd' ;;
        *) return 1 ;;
    esac
    efibootmgr | grep -E "^Boot[0-9A-Fa-f]{4}\*? " | grep -E "$re" | head -1 | sed -E 's/^Boot([0-9A-Fa-f]{4}).*/\1/'
}

need_root() { [ "$(id -u)" = 0 ] || { echo "Serve root." >&2; exit 1; }; }

case "${1:-} ${2:-} ${3:-}" in
    "chime on "|"chime off ")
        need_root
        if [ "$2" = on ]; then setvar StartupMute 00; else setvar StartupMute 01; fi
        echo "Suono di avvio: $2 (vale dalla prossima accensione)." ;;
    "autoboot on "|"autoboot off ")
        need_root
        if [ "$2" = on ]; then setvar AutoBoot 03; else setvar AutoBoot 00; fi
        echo "Accensione aprendo il coperchio / collegando l'alimentatore: $2." ;;
    "boot default opencore"|"boot default linux"|"boot next opencore"|"boot next linux")
        need_root
        command -v efibootmgr >/dev/null || { echo "Serve efibootmgr." >&2; exit 1; }
        n="$(entry "$3")"
        [ -n "$n" ] || { echo "Nessuna voce di avvio per $3 (efibootmgr)." >&2; exit 1; }
        if [ "$2" = next ]; then
            efibootmgr -q -n "$n"
            echo "Prossimo avvio (una volta): Boot$n ($3)."
        else
            order="$(efibootmgr | sed -n 's/^BootOrder: //p' | tr ',' '\n' | grep -vix "$n" | paste -sd, -)"
            efibootmgr -q -o "$n${order:+,$order}"
            echo "Avvio predefinito: Boot$n ($3). Ordine: $(efibootmgr | sed -n 's/^BootOrder: //p')."
        fi ;;
    "status "*)
        echo "StartupMute: $(getvar StartupMute)  (00 = suono di avvio, 01 = muto)"
        echo "AutoBoot: $(getvar AutoBoot)  (assente o 03 = si accende aprendo il coperchio, 00 = no)"
        efibootmgr 2>/dev/null | grep -E '^Boot(Current|Next|Order)' || true ;;
    *) echo "Uso: nvram-control.sh chime on|off | autoboot on|off | boot default|next opencore|linux | status" >&2; exit 1 ;;
esac
