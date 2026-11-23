#!/bin/bash
# Hook systemd-sleep per MacBookPro14,3. Argomenti: $1 = pre|post, $2 = suspend|...
#
# Thunderbolt: durante lo sleep il firmware Apple toglie corrente ai due controller
# Alpine Ridge; il kernel resta fermo 80-100 s (o non riparte) sui bridge spenti.
# Prima dello sleep si rimuovono gli upstream port TB (8086:1578), dopo si fa il
# rescan dei root port. Ricetta e diagnosi: mihneadevries/mbp14-3-linux-sleep-fix
# (commit 4fc3328, provata su 14,3 con kernel 7.2), riscritta qui.
# Effetto collaterale: le periferiche USB-C/TB collegate durante lo sleep possono
# sparire fino al prossimo sleep o riavvio.
#
# Wi-Fi (BCM43602, brcmfmac): driver scaricato prima e ricaricato dopo, scheda
# esclusa da D3cold e wake del suo root port disattivato.
#
# Touch Bar: niente da fare qui. apple-ibridge invia già ASOC.SOCW 0/1 nel suo
# suspend/resume e apple-ib-tb (branch t1-fixes) ha già il .resume per s2idle.
# Non scaricare i moduli della Touch Bar qui: secondo la fonte lo sleep dopo non riparte.

STATE=/run/macbookpro14-3-sleep
log() { echo "$*" | systemd-cat -t macbookpro14-3-sleep; }
# Batteria e causa del risveglio nel journal: le legge scripts/sleep-test.sh report.
battery() {
    local b=/sys/class/power_supply/BAT0
    echo "batteria $(cat $b/capacity 2>/dev/null)% $(( $(cat $b/charge_now 2>/dev/null || echo 0) / 1000 )) mAh ac=$(cat /sys/class/power_supply/ADP1/online 2>/dev/null)"
}
wake_irq() {
    local irq
    irq="$(cat /sys/power/pm_wakeup_irq 2>/dev/null)" || { echo "irq di risveglio: -"; return; }
    echo "irq di risveglio: $irq ($(awk -v i="$irq:" '$1==i {print $NF}' /proc/interrupts))"
}

pre() {
    mkdir -p "$STATE"
    : > "$STATE/rootports"
    local d up root wifi
    for d in /sys/bus/pci/devices/*; do
        [ "$(cat "$d/vendor" 2>/dev/null)" = 0x8086 ] || continue
        [ "$(cat "$d/device" 2>/dev/null)" = 0x1578 ] || continue  # upstream port Alpine Ridge
        up="$(readlink -f "$d")"
        root="$(dirname "$up")"
        basename "$root" >> "$STATE/rootports"
        echo disabled > "$root/power/wakeup" 2>/dev/null
        log "pre $1: rimuovo Thunderbolt $(basename "$up") (root port $(basename "$root"))"
        echo 1 > "$up/remove"
    done

    wifi="$(readlink -f /sys/bus/pci/drivers/brcmfmac/0000:* 2>/dev/null | head -1)"
    if [ -n "$wifi" ]; then
        echo 0 > "$wifi/d3cold_allowed" 2>/dev/null
        echo disabled > "$(dirname "$wifi")/power/wakeup" 2>/dev/null
        log "pre $1: scarico brcmfmac"
        timeout 15 modprobe -r brcmfmac_wcc brcmfmac || log "pre $1: scaricamento brcmfmac fallito"
        : > "$STATE/wifi"
    fi
    log "pre $1: fatto, $(battery)"
}

post() {
    local r
    log "post $1: $(battery), $(wake_irq)"
    sort -u "$STATE/rootports" 2>/dev/null | while read -r r; do
        [ -n "$r" ] || continue
        log "post $1: rescan root port $r"
        echo 1 > "/sys/bus/pci/devices/$r/rescan"
    done
    if [ -e "$STATE/wifi" ]; then
        modprobe brcmfmac || log "post $1: ricaricamento brcmfmac fallito"
        rm -f "$STATE/wifi"
    fi
    # Bluetooth: audio delle chiamate via HCI (scripts/install-bt.sh), se installato.
    [ -x /usr/local/lib/macbookpro14-3/bt-sco-route.py ] && \
        python3 -I /usr/local/lib/macbookpro14-3/bt-sco-route.py hci0 >/dev/null 2>&1
    # Riapplica le impostazioni energetiche (scripts/install-power.sh), se installate.
    [ -x /usr/local/lib/macbookpro14-3/power-source.sh ] && /usr/local/lib/macbookpro14-3/power-source.sh
    set -- "$1" /sys/bus/pci/devices/*
    log "post $1: fatto ($(($# - 1)) funzioni PCI)"
}

case "${1:-}" in
    pre)  pre "${2:-}" ;;
    post) post "${2:-}" ;;
esac
exit 0
