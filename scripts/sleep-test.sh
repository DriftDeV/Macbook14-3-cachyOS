#!/usr/bin/env bash
# Prove di sospensione sul MacBookPro14,3. Il risultato va anche in
# /var/tmp/macbookpro14-3-sleep-test.log (leggibile senza root).
#   scripts/sleep-test.sh check            stato attuale, senza root
#   sudo scripts/sleep-test.sh platform    il kernel fa tutte le fasi e riprende da solo dopo ~5 s,
#                                          senza dormire davvero (pm_test=platform)
#   sudo scripts/sleep-test.sh real [s]    sospensione vera, sveglia RTC dopo s secondi (default 60)
# Se non torna: aspetta almeno 3 minuti prima di forzare lo spegnimento
# (lo stallo Thunderbolt dura 80-100 s). Dopo uno spegnimento forzato, fai uno
# spegnimento pulito e riaccendi: Wi-Fi e T1 possono restare in uno stato strano.
set -u
LOG=/var/tmp/macbookpro14-3-sleep-test.log
mode="${1:-check}"
secs="${2:-60}"

count() {   # quanti percorsi esistono tra quelli dati (glob)
    local n=0 f
    for f in "$@"; do [ -e "$f" ] && n=$((n + 1)); done
    echo "$n"
}
note() {   # il log lo scrive solo root: in /var/tmp un file di un altro utente non è scrivibile
    if [ "$(id -u)" -eq 0 ]; then echo "$*" | tee -a "$LOG"; else echo "$*"; fi
}

state() {
    note "mem_sleep=[$(cat /sys/power/mem_sleep)] pm_async=$(cat /sys/power/pm_async) pm_test=$(grep -o '\[[a-z]*\]' /sys/power/pm_test 2>/dev/null)"
    local d
    for d in /sys/bus/pci/devices/*; do
        [ "$(cat "$d/class")" = 0x010802 ] && note "nvme $(basename "$d") d3cold_allowed=$(cat "$d/d3cold_allowed")"
    done
    note "hook=$( [ -x /usr/lib/systemd/system-sleep/macbookpro14-3-sleep.sh ] && echo si || echo NO)" \
         "sleep.conf: $(systemd-analyze cat-config systemd/sleep.conf 2>/dev/null | grep -E '^(MemorySleepMode|AllowHibernation)=' | tr '\n' ' ')"
    note "pci=$(count /sys/bus/pci/devices/*) xhci=$(count /sys/bus/pci/drivers/xhci_hcd/0000:*)" \
         "wifi=$(count /sys/bus/pci/drivers/brcmfmac/0000:*) t1=$(cat /sys/bus/usb/devices/1-3/idProduct 2>/dev/null)/cfg$(cat /sys/bus/usb/devices/1-3/bConfigurationValue 2>/dev/null)" \
         "touchbar_hid=$(for h in /sys/bus/hid/devices/*05AC:8600*; do basename "$(readlink "$h/driver")"; done | sort | uniq -c | tr -s ' \n' ' ')"
    note "suspend_stats success=$(cat /sys/power/suspend_stats/success) fail=$(cat /sys/power/suspend_stats/fail)"
}

wait_cycle() {   # aspetta che il contatore success/fail cambi (max 300 s)
    local s0="$1" f0="$2" i=0
    while [ "$i" -lt 300 ]; do   # controlla prima: systemctl suspend può tornare già a ripresa avvenuta
        [ "$(cat /sys/power/suspend_stats/success)" != "$s0" ] && return 0
        [ "$(cat /sys/power/suspend_stats/fail)" != "$f0" ] && return 1
        sleep 1; i=$((i + 1))
    done
    return 2
}

run_cycle() {   # $1 = livello pm_test o "none"
    local s0 f0 t0 t1 rc
    s0="$(cat /sys/power/suspend_stats/success)"; f0="$(cat /sys/power/suspend_stats/fail)"
    echo 1 > /sys/power/pm_print_times
    echo "$1" > /sys/power/pm_test
    sync
    t0="$(date +%s)"
    systemctl suspend
    wait_cycle "$s0" "$f0"; rc=$?
    t1="$(date +%s)"
    echo none > /sys/power/pm_test
    echo 0 > /sys/power/pm_print_times
    sleep 5   # lascia finire l'hook post
    case $rc in
        0) note "RISULTATO: ripresa riuscita, $((t1 - t0)) s dall'avvio della sospensione" ;;
        1) note "RISULTATO: sospensione FALLITA (suspend_stats/fail aumentato)" ;;
        *) note "RISULTATO: nessuna ripresa registrata in 300 s" ;;
    esac
    note "--- kernel e hook"
    journalctl --since "@$t0" --no-pager -o short-monotonic \
        | grep -E 'PM: (suspend|resume|noirq|late|early).*(entry|exit|complete)|suspend of devices|resume of devices|macbookpro14-3-sleep|inaccessible|Unable to change power state|failed to (suspend|resume)|amdgpu.*(fail|timeout)|Touchbar|apple-ib|brcmfmac.*(error|fail)|nvme.*(timeout|reset)' \
        | tail -60 | while IFS= read -r l; do note "$l"; done
    note "--- stato dopo"
    state
}

note "=== $(date -Is) mode=$mode kernel=$(uname -r) ac=$(cat /sys/class/power_supply/ADP1/online 2>/dev/null) batt=$(cat /sys/class/power_supply/BAT0/capacity 2>/dev/null)%"
case "$mode" in
    check) state ;;
    platform|devices)
        [ "$(id -u)" -eq 0 ] || { echo "Serve sudo." >&2; exit 1; }
        state; run_cycle "$mode" ;;
    real)
        [ "$(id -u)" -eq 0 ] || { echo "Serve sudo." >&2; exit 1; }
        state
        rtcwake -m no -s "$secs" >/dev/null && note "sveglia RTC tra $secs s"
        run_cycle none ;;
    *) echo "Uso: $0 check | platform | real [secondi]" >&2; exit 1 ;;
esac
[ "$(id -u)" -eq 0 ] && chmod 644 "$LOG" && echo "Log: $LOG"
exit 0
