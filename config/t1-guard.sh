#!/bin/bash
# Guardia del firmware del T1 (MacBookPro14,3). Il T1 non ha firmware proprio: a ogni accensione il firmware del Mac lo
# carica da EFI/APPLE/EMBEDDEDOS/ della partizione EFI di Apple (combined.memboot, FDRData, version.plist). Se quei file
# spariscono il T1 parte in recovery (05ac:1281) e Touch Bar, webcam, Touch ID e sensore di luce si spengono.
#
#   t1-guard.sh init      prende come riferimento i file attuali (solo se il T1 funziona, 05ac:8600)
#   t1-guard.sh check     (servizio, a ogni avvio) confronta, annota, e se i file mancano o sono rovinati li ripristina
#   t1-guard.sh restore   ripristina subito i file dal riferimento
#   t1-guard.sh status    stato e ultime righe della cronologia
#
# Riferimento e cronologia in /var/lib/macbookpro14-3/t1-guard/ (history.log: una riga per avvio; manifest-*.txt: elenco
# di tutti i file della ESP con dimensione e data, per capire chi ci scrive). Stato per MacBook Manager in last.json.
# Se il firmware è cambiato ma il T1 funziona (aggiornamento legittimo), il nuovo diventa il riferimento.
# Installato da install.sh (passo kernel) come /usr/local/lib/macbookpro14-3/t1-guard.sh.
set -u
STATE=/var/lib/macbookpro14-3/t1-guard
REF="$STATE/EMBEDDEDOS"
MNT=/run/macbookpro14-3/t1-guard-mnt
FILES="combined.memboot FDRData version.plist"
ESP_TYPE=c12a7328-f81f-11d2-ba4b-00a0c93ec93b

log() { echo "$*" | systemd-cat -t macbookpro14-3-t1-guard -p "${2:-info}"; echo "$*"; }

t1_id() {   # 8600 (funziona), 1281 (recovery) o assente
    local d
    for d in /sys/bus/usb/devices/*/; do
        [ "$(cat "$d/idVendor" 2>/dev/null)" = 05ac ] || continue
        case "$(cat "$d/idProduct" 2>/dev/null)" in 8600|1281) cat "$d/idProduct"; return ;; esac
    done
    echo assente
}

mount_any() {   # mount_any ro|rw dev dir: se dev è già montata altrove (es. /boot/efi in rw) Linux rifiuta un modo
    # diverso ("would change RO state"): in quel caso la seconda vista usa il modo già in uso
    mount -o "$1" "$2" "$3" >/dev/null 2>&1 && return 0   # l'avviso "would change RO state" esce su stdout
    local cur
    cur="$(findmnt -rno OPTIONS --source "$2" | head -1 | cut -d, -f1)"
    [ -n "$cur" ] && mount -o "$cur" "$2" "$3" >/dev/null 2>&1
}

find_esp() {   # la partizione EFI con EFI/APPLE (la prima, se più d'una); vuoto se nessuna
    local p probe
    probe="$(mktemp -d)"
    for p in $(lsblk -rno PATH,PARTTYPE | awk -v t="$ESP_TYPE" 'tolower($2)==t{print $1}'); do
        if mount_any ro "$p" "$probe"; then
            if [ -d "$probe/EFI/APPLE" ]; then umount "$probe"; rmdir "$probe"; echo "$p"; return; fi
            umount "$probe"
        fi
    done
    rmdir "$probe"
}

mount_esp() {   # mount_esp ro|rw: monta la ESP di Apple in $MNT (anche se è già montata altrove)
    mkdir -p "$MNT"
    mountpoint -q "$MNT" && umount "$MNT"
    mount_any "$1" "$ESP" "$MNT"
}

file_sha() { [ -f "$1" ] && sha256sum "$1" | cut -c1-64 || echo assente; }

write_state() {   # write_state stato messaggio
    mkdir -p "$STATE"
    printf '{"ts": %d, "status": "%s", "t1": "%s", "esp": "%s", "message": "%s"}\n' \
        "$(date +%s)" "$1" "$(t1_id)" "${ESP:-}" "$2" > "$STATE/last.json.tmp"
    chmod 644 "$STATE/last.json.tmp"; mv -f "$STATE/last.json.tmp" "$STATE/last.json"
}

restore_files() {
    log "ripristino del firmware del T1 da $REF su $ESP" warning
    mount_esp rw || { log "montaggio in scrittura di $ESP non riuscito" err; return 1; }
    mkdir -p "$MNT/EFI/APPLE/EMBEDDEDOS"
    for f in $FILES; do cp -f "$REF/$f" "$MNT/EFI/APPLE/EMBEDDEDOS/$f.tmp" && mv -f "$MNT/EFI/APPLE/EMBEDDEDOS/$f.tmp" "$MNT/EFI/APPLE/EMBEDDEDOS/$f"; done
    sync
    local ok=1
    for f in $FILES; do [ "$(file_sha "$MNT/EFI/APPLE/EMBEDDEDOS/$f")" = "$(file_sha "$REF/$f")" ] || ok=0; done
    umount "$MNT"
    [ "$ok" = 1 ]
}

cmd="${1:-check}"
[ "$(id -u)" = 0 ] || { echo "Serve root." >&2; exit 1; }
mkdir -p "$STATE"
ESP="$(find_esp)"
t1="$(t1_id)"

case "$cmd" in
    init)
        [ -n "$ESP" ] || { log "Nessuna partizione EFI con EFI/APPLE: impossibile prendere il riferimento." err; exit 1; }
        [ "$t1" = 8600 ] || { log "Il T1 non funziona ($t1): non prendo come riferimento questi file." err; exit 1; }
        mount_esp ro || exit 1
        mkdir -p "$REF"
        for f in $FILES; do cp -f "$MNT/EFI/APPLE/EMBEDDEDOS/$f" "$REF/$f"; done
        # shellcheck disable=SC2086  # elenco fisso di nomi senza spazi
        (cd "$REF" && sha256sum $FILES > ../ref.sha256)
        umount "$MNT"
        log "riferimento preso da $ESP ($(awk '/<string>/{gsub(/<[^>]*>|[ \t]/,"");print;exit}' "$REF/version.plist"))"
        write_state ok "riferimento preso"
        ;;
    restore)
        [ -s "$STATE/ref.sha256" ] || { echo "Nessun riferimento: prima t1-guard.sh init." >&2; exit 1; }
        [ -n "$ESP" ] || { log "Partizione EFI di Apple non trovata: ripristina l'immagine (docs/t1-firmware.md)." err; exit 1; }
        if restore_files; then
            write_state restored "firmware del T1 ripristinato: spegni completamente il Mac"
            log "ripristinato: SPEGNI completamente il Mac e riaccendi dopo 30 s" warning
        else
            write_state error "ripristino non riuscito"; exit 1
        fi
        ;;
    status)
        cat "$STATE/last.json" 2>/dev/null
        echo "T1 adesso: $t1, ESP di Apple: ${ESP:-non trovata}"
        tail -n 8 "$STATE/history.log" 2>/dev/null
        ;;
    check)
        stamp="$(date '+%F %T')"
        if [ ! -s "$STATE/ref.sha256" ]; then
            if [ "$t1" = 8600 ] && [ -n "$ESP" ]; then "$0" init >/dev/null; fi
            exit 0
        fi
        if [ -z "$ESP" ]; then
            echo "$stamp t1=$t1 esp=NESSUNA" >> "$STATE/history.log"
            log "ALLARME: nessuna partizione EFI con EFI/APPLE. Il firmware del T1 è altrove nel backup: ripristino a mano (docs/t1-firmware.md)." err
            write_state missing-esp "partizione EFI di Apple sparita"
            exit 0
        fi
        mount_esp ro || exit 1
        # elenco di tutta la ESP (dimensione e data), per vedere chi ci scrive fra un avvio e l'altro
        man="$STATE/manifest-$(date +%Y%m%d-%H%M%S).txt"
        (cd "$MNT" && find . -type f -printf '%s %TY-%Tm-%Td %TH:%TM %p\n' | sort -k4) > "$man"
        prev=""
        for m in "$STATE"/manifest-*.txt; do [ -e "$m" ] && [ "$m" != "$man" ] && prev="$m"; done
        changed=""
        if [ -n "$prev" ] && ! cmp -s "$prev" "$man"; then
            changed="$(diff "$prev" "$man" | grep -c '^[<>]') righe diverse"
        elif [ -n "$prev" ]; then
            rm -f "$man"    # niente di nuovo: tengo solo l'ultimo diverso
        fi
        find "$STATE" -maxdepth 1 -name 'manifest-*.txt' -printf '%T@ %p\n' | sort -rn | tail -n +31 | cut -d' ' -f2- \
            | xargs -r rm -f
        bad="" stat=""
        for f in $FILES; do
            cur="$(file_sha "$MNT/EFI/APPLE/EMBEDDEDOS/$f")"
            refs="$(awk -v f="$f" '$2==f{print $1}' "$STATE/ref.sha256")"
            if [ "$cur" = "$refs" ]; then stat="$stat $f=ok"
            elif [ "$cur" = assente ]; then stat="$stat $f=ASSENTE"; bad="$bad $f"
            else stat="$stat $f=DIVERSO"; bad="$bad $f"; fi
        done
        umount "$MNT"
        echo "$stamp t1=$t1 esp=$ESP$stat${changed:+ esp:$changed}" >> "$STATE/history.log"
        if [ -z "$bad" ]; then
            write_state ok "firmware del T1 integro${changed:+ (altri file della ESP cambiati: $changed)}"
            [ "$t1" = 1281 ] && log "T1 in recovery con il firmware integro: spegnimento completo e riaccensione." warning
        elif [ "$t1" = 8600 ] && ! grep -q ASSENTE <<< "$stat"; then
            # cambiato ma funziona: aggiornamento legittimo, il nuovo diventa il riferimento (il vecchio resta da parte)
            mv "$REF" "$REF.$(date +%Y%m%d-%H%M%S)"
            "$0" init >/dev/null
            log "firmware del T1 cambiato (${bad# }) e funzionante: nuovo riferimento" warning
        elif restore_files; then
            write_state restored "firmware del T1 ripristinato (${bad# }): spegni completamente il Mac"
            log "firmware del T1 rovinato o mancante (${bad# }): ripristinato. Spegni completamente il Mac." warning
        else
            write_state error "firmware del T1 rovinato (${bad# }) e ripristino non riuscito"
            log "firmware del T1 rovinato (${bad# }) e ripristino NON riuscito" err
        fi
        ;;
    *) echo "Uso: t1-guard.sh init|check|restore|status" >&2; exit 2 ;;
esac
exit 0
