#!/bin/sh
# SPERIMENTALE [NV]: il T1 parte in una configurazione USB limitata (senza
# webcam UVC). Questo script prova a portarlo alla configurazione 2.
# Le fonti indicano che dopo un aggiornamento kernel serve rifarlo
# (cschaba/macbookpro14-3-linux, fix-touchbar-t1.sh). Non è abilitato di default.
CONF="${1:-2}"
for d in /sys/bus/usb/devices/*; do
    [ -r "$d/idVendor" ] || continue
    if [ "$(cat "$d/idVendor")" = "05ac" ] && [ "$(cat "$d/idProduct")" = "8600" ]; then
        echo "iBridge/T1 trovato in $d (config attuale: $(cat "$d/bConfigurationValue"))"
        echo "$CONF" > "$d/bConfigurationValue" && echo "Impostata configurazione $CONF"
        exit 0
    fi
done
echo "Dispositivo 05ac:8600 non trovato" >&2
exit 1
