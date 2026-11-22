#!/bin/sh
# Disabilita d3cold sull'NVMe. L'indirizzo PCI NON è fisso: sul 14,3 lo slot
# 01:00.0 è la Radeon, quindi si cerca per classe PCI (0x0108 = NVMe).
# Ricetta di mihneadevries/mbp14-3-linux-sleep-fix, non verificata qui.
for dev in /sys/bus/pci/devices/*; do
    [ -r "$dev/class" ] || continue
    case "$(cat "$dev/class")" in
        0x0108*)
            if [ -w "$dev/d3cold_allowed" ]; then
                echo 0 > "$dev/d3cold_allowed"
                echo "d3cold disabilitato su $dev"
            fi
            ;;
    esac
done
exit 0
