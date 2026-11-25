#!/bin/bash
# All'avvio (dopo la rete): se ai driver della repo manca la versione per il kernel in uso, li ricompila con DKMS.
# Rete di sicurezza per gli aggiornamenti del kernel: di solito ci pensa il hook DKMS di pacman, ma se in quel momento
# mancava la rete i moduli che scaricano i sorgenti da kernel.org (audio, webcam) restano indietro.
# Installato da install.sh (passo kernel) come /usr/local/lib/macbookpro14-3/dkms-catchup.sh.
MODS="appleibridge apple-ibridge snd_hda_macbookpro t1bridge-appletbdrm t1bridge-uvc t1bridge-ncm"
kv="$(uname -r)"
log() { echo "$*" | systemd-cat -t macbookpro14-3-dkms; }
command -v dkms >/dev/null || exit 0
missing=""
for m in $MODS; do
    for v in $(dkms status "$m" 2>/dev/null | sed -nE 's#^[^/]+/([^,]+),.*#\1#p' | sort -u); do
        dkms status "$m/$v" -k "$kv" 2>/dev/null | grep -q 'installed' || missing="$missing $m/$v"
    done
done
[ -n "$missing" ] || exit 0
log "driver mancanti per $kv:$missing: li ricompilo"
ok=""
for mv in $missing; do
    if dkms build "$mv" -k "$kv" >/dev/null 2>&1 && dkms install "$mv" -k "$kv" --force >/dev/null 2>&1; then
        ok="$ok $mv"
    else
        log "$mv: compilazione per $kv non riuscita (vedi /var/lib/dkms/${mv%/*}/${mv#*/}/build/make.log)"
    fi
done
[ -n "$ok" ] && log "ricompilati per $kv:$ok. Riavvia per usarli."
exit 0
