#!/bin/sh
# Hook systemd-sleep. Argomenti: $1 = pre|post, $2 = suspend|hibernate|...
# Scarica brcmfmac prima della sospensione e lo ricarica dopo (fonte: sleep-fix repo).
# NON gestisce ancora la rimozione degli upstream port Thunderbolt: vedi docs/.
case "$1" in
    pre)
        modprobe -r brcmfmac_wcc 2>/dev/null
        modprobe -r brcmfmac 2>/dev/null
        ;;
    post)
        modprobe brcmfmac 2>/dev/null
        /usr/local/lib/macbookpro14-3/d3cold-nvme.sh >/dev/null 2>&1
        ;;
esac
exit 0
