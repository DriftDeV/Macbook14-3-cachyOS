#!/usr/bin/env bash
# Prove di sospensione sul MacBookPro14,3. Il risultato va anche in
# /var/tmp/macbookpro14-3-sleep-test.log (leggibile senza root).
#   scripts/sleep-test.sh check            stato attuale, senza root
#   sudo scripts/sleep-test.sh platform    il kernel fa tutte le fasi e riprende da solo dopo ~5 s,
#                                          senza dormire davvero (pm_test=platform)
#   sudo scripts/sleep-test.sh real [s]    sospensione vera, sveglia RTC dopo s secondi (default 60)
#   scripts/sleep-test.sh report [boot]    senza root: ogni sospensione dell'avvio attuale (o -1, -2...):
#                                          durata, modalità, causa del risveglio, batteria consumata
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

report() {   # dati dal journal: logind (coperchio), systemd-sleep, kernel, hook macbookpro14-3-sleep
    journalctl -b "${1:-0}" -o short-unix --no-pager -q 2>/dev/null \
        | grep -E 'Lid (closed|opened)|Performing sleep operation|returned from sleep operation|PM: suspend entry|macbookpro14-3-sleep.*(pre suspend: fatto|post suspend: batteria)' \
        | python3 -I -c '
import re, sys, time
cyc, cur, lid, opened = [], None, "?", 0.0
for l in sys.stdin:
    t, msg = float(l.split()[0]), l
    if "Lid closed" in msg: lid = "chiuso"
    elif "Lid opened" in msg:
        lid, opened = "aperto", t
        if cur and cur.get("end") and t - cur["end"] <= 5: cur["cause"] = "coperchio aperto"
    elif "Performing sleep operation" in msg:
        cur = {"start": t, "lid": lid, "mode": "?"}; cyc.append(cur)
    elif cur and "PM: suspend entry" in msg: cur["mode"] = re.search(r"\((\w+)\)", msg).group(1)
    elif cur and "pre suspend: fatto" in msg:
        m = re.search(r"(\d+)% (\d+) mAh ac=(\d)", msg)   # le righe dei vecchi hook non hanno la batteria
        if m: cur["b0"] = m.groups()
    elif cur and "returned from sleep" in msg:
        cur["end"] = t
        if t - opened <= 5: cur["cause"] = "coperchio aperto"   # logind può scriverlo prima di systemd-sleep
    elif cur and "post suspend: batteria" in msg:
        m = re.search(r"(\d+)% (\d+) mAh", msg)
        if m: cur["b1"] = m.groups()
        m = re.search(r"irq di risveglio: (.*)", msg); cur["irq"] = m.group(1).strip() if m else "-"
if not cyc: print("Nessuna sospensione in questo avvio."); sys.exit()
spont = 0
print("%-14s %7s %-7s %-9s %-26s %s" % ("inizio", "durata", "modo", "coperchio", "batteria", "risveglio"))
for c in cyc:
    if "end" not in c: print(time.strftime("%d/%m %H:%M:%S", time.localtime(c["start"])), "  nessun ritorno registrato"); continue
    d = (c["end"] - c["start"]) / 60
    cause = c.get("cause") or ("SENZA aprire il coperchio" if c["lid"] == "chiuso" else "tasto, sveglia o altro")
    if c["lid"] == "chiuso" and not c.get("cause"): spont += 1
    bat = "-"
    if "b0" in c and "b1" in c:
        dm = int(c["b0"][1]) - int(c["b1"][1])
        bat = "%s%%->%s%% %d mAh" % (c["b0"][0], c["b1"][0], dm) + (" (%.0f mAh/h)" % (dm / (d / 60)) if d >= 10 and c["b0"][2] == "0" else "")
    print("%-14s %5.0fm  %-7s %-9s %-26s %s [irq %s]" % (time.strftime("%d/%m %H:%M:%S", time.localtime(c["start"])), d, c["mode"], c["lid"], bat, cause, c.get("irq", "-")))
print()
print("Sospensioni: %d, risvegli a coperchio chiuso senza aprirlo: %d" % (len(cyc), spont))
print("Consumo atteso a batteria (mAh/h, solo sospensioni >= 10 min): S3 poche decine; s2idle diverse centinaia.")
'
}

note "=== $(date -Is) mode=$mode kernel=$(uname -r) ac=$(cat /sys/class/power_supply/ADP1/online 2>/dev/null) batt=$(cat /sys/class/power_supply/BAT0/capacity 2>/dev/null)%"
case "$mode" in
    check) state ;;
    report) report "${2:-0}"; exit 0 ;;
    platform|devices)
        [ "$(id -u)" -eq 0 ] || { echo "Serve sudo." >&2; exit 1; }
        state; run_cycle "$mode" ;;
    real)
        [ "$(id -u)" -eq 0 ] || { echo "Serve sudo." >&2; exit 1; }
        state
        rtcwake -m no -s "$secs" >/dev/null && note "sveglia RTC tra $secs s"
        run_cycle none ;;
    *) echo "Uso: $0 check | report [boot] | platform | real [secondi]" >&2; exit 1 ;;
esac
[ "$(id -u)" -eq 0 ] && chmod 644 "$LOG" && echo "Log: $LOG"
exit 0
