#!/usr/bin/env bash
# PROVA di Touch ID sul MacBookPro14,3 con T1Bridge (docs/touchid-t1.md). Annullabile con "undo".
# Installa SOLO i pezzi di Touch ID, compilati dal commit fissato in config/sources.conf:
#   t1-ncm-ready, t1-xart-storage, t1-keybag-relay, t1-touchid-auth (broker), CLI t1bridge;
#   driver della rete privata apple_t1_ncm (DKMS dkms/t1bridge-ncm); libfprint/fprintd di T1Bridge (makepkg).
# NON installa: il pacchetto t1bridge-dkms (blocca apple_ibridge e romperebbe la sospensione), t1_cfgsel,
# la recovery del T1 (t1-legacy-recovery, /dev/t1bridge-recovery), l'import automatico, nulla nel PAM di sudo.
# Richiede la Touch Bar in modalità display (configurazione USB 2: rete privata e Secure Enclave ci sono solo lì).
#
#   sudo scripts/install-touchid.sh [install] [--dry-run]   passi 1-4 della procedura (dipendenze, build, servizi,
#                                                        rete t1ncm, regola ufw per xART, niente impronta sul blocco)
#   sudo scripts/install-touchid.sh status                  stato di servizi, rete, firewall, dati Apple, impronte
#   sudo scripts/install-touchid.sh import [FDRData]        passo 6: importa i dati di fabbrica (sola lettura) dal
#                                                        backup della ESP Apple (predefinito: il più recente)
#   sudo scripts/install-touchid.sh undo [--yes]            rollback completo (cancella le impronte Linux, archivia
#                                                        /var/lib/t1bridge in /var/backups/macbookpro14-3)
#   sudo scripts/install-touchid.sh lockscreen on|off       impronta nella schermata di blocco di KDE (spenta all'inizio)
#   sudo scripts/install-touchid.sh sudo on|off             impronta per sudo (la password resta sempre valida)
# Gli interruttori sono /usr/local/bin/touchid-pam (scripts/touchid-pam.sh), usato anche da MacBook Manager.
# Registrazione e verifica restano a mano, da Konsole nella sessione grafica (Polkit), vedi la fine dell'installazione.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=scripts/lib.sh
source "$SCRIPT_DIR/lib.sh"
# shellcheck source=config/sources.conf
source "$REPO_DIR/config/sources.conf"

L=/usr/local/lib/macbookpro14-3/t1bridge
CLI=/usr/local/bin/t1bridge
C="$REPO_DIR/config/t1bridge/touchid"
STATE=/var/lib/macbookpro14-3/touchid.state
BACKUPS=/var/backups/macbookpro14-3
VER=0.1.12
IFACE=t1ncm
PEER=fe80::aede:48ff:fe33:4455   # BRIDGEOS_XART_PEER in crates/t1-daemons/src/xart_service.rs (81cbdf8)
UNITS="t1-ncm-ready@.service t1-xart-storage@.service t1bridge-keybag.service t1-touchid-auth.service
       t1-touchid-auth.socket t1bridge-fingerprint.socket"
SOCKETS=(t1-touchid-auth.socket t1bridge-fingerprint.socket)
BINS="t1-ncm-ready t1-xart-storage t1-keybag-relay t1-touchid-auth"
PKGS="libfprint-t1bridge fprintd-t1bridge"
MAKEDEPS="meson gtk-doc gobject-introspection glib2-devel pam_wrapper python-dbus python-dbusmock python-packaging
          python-cairo python-gobject libgusb libgudev pixman openssl"

CMD=install
PAM_TOGGLE=/usr/local/bin/touchid-pam
for a in "$@"; do
    case "$a" in
        install|status|import|undo) CMD="$a" ;;
        lockscreen|sudo) CMD="$a" ;;
        on|off) ONOFF="$a" ;;
        --dry-run) DRY_RUN=1 ;;
        --yes) ASSUME_YES=1 ;;
        /*) FDR_ARG="$a" ;;
        *) die "Opzione sconosciuta: $a (install|status|import [FDRData]|undo, --dry-run, --yes)" ;;
    esac
done
need_root
USER_NAME="${SUDO_USER:-}"
[ -z "$USER_NAME" ] && [ "$DRY_RUN" = 1 ] && USER_NAME="$(id -un)"
[ -n "$USER_NAME" ] && [ "$USER_NAME" != root ] || die "Lancialo con sudo dal tuo utente."
USER_HOME="$(getent passwd "$USER_NAME" | cut -d: -f6)"
SRC="${T1BRIDGE_SRC:-$USER_HOME/src/t1bridge}"
OUT="${T1BUILD:-$USER_HOME/src/t1bridge-build}"
BUILD="$OUT/target/release"

as_user() {
    if [ "$DRY_RUN" = 1 ]; then echo "[dry-run] (come $USER_NAME) $*"; return 0; fi
    # PATH di login di Arch: fprintd usa pod2man da /usr/bin/core_perl.
    runuser -u "$USER_NAME" -- env HOME="$USER_HOME" \
        PATH="/usr/local/sbin:/usr/local/bin:/usr/bin:/usr/bin/site_perl:/usr/bin/vendor_perl:/usr/bin/core_perl" "$@"
}
state_get() { [ -r "$STATE" ] && sed -n "s/^$1=//p" "$STATE" | tail -1; }
state_set() {
    [ "$DRY_RUN" = 1 ] && { echo "[dry-run] $STATE: $1=$2"; return 0; }
    install -d -m755 "$(dirname "$STATE")"
    touch "$STATE"; sed -i "/^$1=/d" "$STATE"; echo "$1=$2" >> "$STATE"
}
latest_fdr() { find "$BACKUPS" -maxdepth 4 -path '*/EFI-APPLE-*/EMBEDDEDOS/FDRData' -type f 2>/dev/null | sort | tail -1; }
ufw_active() {
    command -v ufw >/dev/null || return 1
    if [ "$(id -u)" -eq 0 ]; then ufw status 2>/dev/null | grep -q '^Status: active'
    else grep -qs '^ENABLED=yes' /etc/ufw/ufw.conf; fi   # --dry-run senza sudo
}
# ufw_rule "allow" [comment ...] | ufw_rule "delete allow"
ufw_rule() {
    local act="$1"; shift
    # shellcheck disable=SC2086  # "delete allow" sono due parole
    ufw $act in on "$IFACE" proto tcp from "$PEER" to any port 61500 "$@"
}
t1_config() {
    local d
    for d in /sys/bus/usb/devices/*; do
        [ "$(cat "$d/idVendor" 2>/dev/null)" = 05ac ] && [ "$(cat "$d/idProduct" 2>/dev/null)" = 8600 ] \
            && { cat "$d/bConfigurationValue"; return 0; }
    done
    echo "?"
}

# ------------------------------------------------------------------------------------------- status
do_status() {
    echo "T1 configurazione USB: $(t1_config) (Touch ID richiede 2 = modalità display)"
    echo "modulo apple_t1_ncm: $([ -d /sys/module/apple_t1_ncm ] && echo caricato || echo no)   rete $IFACE: $(cat /sys/class/net/$IFACE/operstate 2>/dev/null || echo assente)"
    local u
    for u in t1-ncm-ready@$IFACE.service t1-xart-storage@$IFACE.service t1bridge-keybag.service \
             t1-touchid-auth.service "${SOCKETS[@]}" fprintd.service; do
        printf '  %-34s %s\n' "$u" "$(systemctl is-active "$u" 2>/dev/null)"
    done
    if ufw_active; then
        echo "ufw: attivo; regola xART: $(ufw status | grep -q "61500/tcp on $IFACE" && echo presente || echo MANCANTE)"
    fi
    echo "dati Apple importati: $([ -n "$(find /var/lib/t1bridge/machine-data -mindepth 1 -print -quit 2>/dev/null)" ] && echo sì || echo no)"
    echo "keybag: $([ -e /var/lib/t1bridge/touch-id/keybag.state ] && echo creata || echo 'non ancora (la crea la prima registrazione)')"
    [ -x "$CLI" ] && { echo "--- t1bridge status"; "$CLI" status || true; }
    command -v fprintd-list >/dev/null && { echo "--- impronte di $USER_NAME"; fprintd-list "$USER_NAME" 2>&1 | sed 's/^/  /' || true; }
}

# ------------------------------------------------------------------------------------------- import
do_import() {
    [ -x "$CLI" ] || die "Touch ID non installato: prima sudo scripts/install-touchid.sh"
    local fdr="${FDR_ARG:-$(latest_fdr)}"
    [ -n "$fdr" ] && [ -f "$fdr" ] || die "FDRData non trovato in $BACKUPS: lancia prima sudo scripts/backup-esp.sh"
    log "Importo i dati di fabbrica del sensore da $fdr (sola lettura; la sorgente deve essere di QUESTO Mac)"
    set +e; run "$CLI" machine-data import --from "$fdr"; local rc=$?; set -e
    if [ "$rc" = 0 ]; then ok "Importati in /var/lib/t1bridge/machine-data."
    else
        warn "Import non riuscito (codice $rc). Fermati qui: NON usare la recovery (machine-data recover) né cancellare"
        warn "/var/lib/t1bridge. Controlla: sudo $CLI status, journalctl -b -t t1bridge."
        exit "$rc"
    fi
}

# ------------------------------------------------------------------------------------------- undo
do_undo() {
    warn "Rollback di Touch ID: impronte Linux cancellate, servizi e pacchetti rimossi, stato archiviato."
    confirm "Procedo?" || die "Annullato."
    if command -v fprintd-list >/dev/null && fprintd-list "$USER_NAME" 2>/dev/null | grep -qE '^ +- #'; then
        log "Cancello le impronte Linux di $USER_NAME (prima di tutto: serve il broker attivo)"
        run systemctl start "${SOCKETS[@]}" 2>/dev/null || true
        run fprintd-delete "$USER_NAME" || warn "fprintd-delete non riuscito: l'impronta può restare nel Secure Enclave (issue #57)."
    fi
    log "Fermo e disabilito i servizi"
    run systemctl disable --now "${SOCKETS[@]}" 2>/dev/null || true
    run systemctl stop t1-touchid-auth.service t1bridge-keybag.service 't1-xart-storage@*' 't1-ncm-ready@*' fprintd.service 2>/dev/null || true
    log "Pacchetti libfprint/fprintd di T1Bridge e dipendenze di compilazione installate dallo script"
    local p rm=()
    for p in $PKGS; do pacman -Q "$p" >/dev/null 2>&1 && rm+=("$p"); done
    [ "${#rm[@]}" -gt 0 ] && run pacman -R --noconfirm "${rm[@]}"
    rm=()
    for p in $(state_get ASDEPS); do pacman -Qd "$p" >/dev/null 2>&1 && rm+=("$p"); done
    [ "${#rm[@]}" -gt 0 ] && { run pacman -Rns --noconfirm "${rm[@]}" || warn "Alcune dipendenze sono usate da altro: restano."; }
    log "Programmi, unit, regole"
    for p in $BINS; do run rm -f "$L/$p"; done
    run rm -f "$CLI"
    for p in $UNITS; do run rm -f "/etc/systemd/system/$p"; done
    run rm -f /etc/udev/rules.d/90-t1bridge-xart.rules /etc/systemd/network/49-macbookpro14-3-t1ncm.link \
        /etc/sysusers.d/t1bridge.conf /etc/tmpfiles.d/t1bridge.conf /etc/t1bridge/diagnostics.conf
    run rmdir /etc/t1bridge 2>/dev/null || true
    if [ -x "$PAM_TOGGLE" ]; then
        run "$PAM_TOGGLE" sudo off || warn "Controlla /etc/pam.d/sudo (copia in /etc/pam.d/sudo.touchid-pam.bak)."
        run "$PAM_TOGGLE" lockscreen on || true
    fi
    run rm -f "$PAM_TOGGLE" /etc/pam.d/sudo.touchid-pam.bak
    if [ "$(state_get UFW)" = 1 ] && ufw_active; then run ufw_rule "delete allow" || true; fi
    if [ -d /var/lib/t1bridge ]; then
        local arch; arch="$BACKUPS/t1bridge-state-$(date +%Y%m%d-%H%M%S).tar"
        log "Archivio lo stato protetto in $arch (0600, root) e lo tolgo dal sistema"
        run install -d -m700 "$BACKUPS"
        if [ "$DRY_RUN" = 1 ]; then echo "[dry-run] tar -cf $arch -C /var/lib t1bridge"
        else (umask 077; tar -cf "$arch" -C /var/lib t1bridge); fi
        run rm -rf /var/lib/t1bridge
    fi
    run rm -rf /run/t1bridge /run/t1-touchid
    getent group t1bridge >/dev/null && run groupdel t1bridge || true
    log "Driver della rete privata"
    [ -d /sys/module/apple_t1_ncm ] && run rmmod apple_t1_ncm || true
    run dkms remove "t1bridge-ncm/$VER" --all >/dev/null 2>&1 || true
    run rm -rf "/usr/src/t1bridge-ncm-$VER"
    run rm -f "$STATE"
    run systemctl daemon-reload
    run udevadm control --reload
    ok "Rimosso. Ora: spegnimento completo (~30 s), poi avvia macOS e controlla che Touch ID funzioni ancora."
}

# ------------------------------------------------------------------------------------------- install
do_install() {
    check_model
    # Touch ID usa la configurazione USB 2 del T1: basta la modalità display salvata (install.sh la attiva al riavvio).
    LIVE=0
    if [ "$(cat /run/macbookpro14-3/touchbar/mode 2>/dev/null)" = display ] && [ "$(t1_config)" = 2 ]; then LIVE=1
    elif grep -qs '^TOUCHBAR_MODE=display' /etc/macbookpro14-3/touchbar.conf; then
        warn "Modalità display salvata ma non ancora attiva: installo, Touch ID partirà dopo il riavvio."
    else
        die "Touch ID richiede la Touch Bar in modalità display: sudo touchbar-mode set display (in tastiera non c'è)."
    fi
    pacman -Q t1bridge-dkms >/dev/null 2>&1 && die "Il pacchetto t1bridge-dkms è installato: blocca apple_ibridge e rompe la sospensione. Rimuovilo prima."
    [ -d "$SRC/.git" ] || die "Manca $SRC: lancia prima scripts/build-t1bridge.sh (da utente)."
    [ "$(git -C "$SRC" rev-parse HEAD)" = "$T1BRIDGE_REF" ] || die "$SRC non è al commit $T1BRIDGE_REF."
    [ -z "$(git -C "$SRC" status --porcelain)" ] || die "$SRC ha modifiche locali: mi fermo."
    local fdr; fdr="$(latest_fdr)"
    [ -n "$fdr" ] || die "Nessun backup con FDRData in $BACKUPS: lancia prima sudo scripts/backup-esp.sh (passo 0)."
    ok "Backup dei dati di fabbrica: $fdr"
    for c in dkms cargo makepkg; do command -v "$c" >/dev/null || die "$c non installato."; done
    [ "$(cat /sys/class/power_supply/ADP1/online 2>/dev/null)" = 1 ] || warn "Alimentatore scollegato: meglio collegarlo per la prova."

    log "Dipendenze di compilazione (solo quelle mancanti, segnate come dipendenze: undo le toglie)"
    local p miss=()
    for p in $MAKEDEPS; do pacman -Q "$p" >/dev/null 2>&1 || miss+=("$p"); done
    if [ "${#miss[@]}" -gt 0 ]; then
        run pacman -S --needed --noconfirm --asdeps "${miss[@]}"
        state_set ASDEPS "$(state_get ASDEPS) ${miss[*]}"
    fi

    log "Compilo i servizi Touch ID di T1Bridge $T1BRIDGE_TAG (da utente, versioni fissate da Cargo.lock)"
    local spec crate bin feat extra
    for spec in "t1-daemons t1-xart-storage -" "t1-daemons t1-ncm-ready -" \
                "t1-daemons t1-keybag-relay keybag-relay-service" "t1-daemons t1-touchid-auth auth-broker-service" \
                "t1-import t1bridge -"; do
        read -r crate bin feat <<< "$spec"
        extra=(); [ "$feat" = - ] || extra=(--features "$feat")   # una build per binario, come il PKGBUILD
        as_user env CARGO_TARGET_DIR="$OUT/target" cargo build --manifest-path "$SRC/Cargo.toml" \
            --release --locked -p "$crate" --bin "$bin" "${extra[@]}"
    done

    log "libfprint e fprintd con il driver T1Bridge (makepkg, sorgenti con sha256 fissati nei PKGBUILD)"
    # In ordine: fprintd si compila solo con libfprint-t1bridge già installata (pkg-config libfprint-2).
    local pkgdir="$OUT/pkg" file
    as_user mkdir -p "$pkgdir/build" "$pkgdir/src" "$pkgdir/out"
    for p in $PKGS; do
        local mk=(env BUILDDIR="$pkgdir/build" SRCDEST="$pkgdir/src" PKGDEST="$pkgdir/out" makepkg)
        if [ "$DRY_RUN" = 1 ]; then
            as_user "${mk[@]}" -f --nocheck --noconfirm --nodeps; run pacman -U --noconfirm "<$p>"; continue
        fi
        file="$(cd "$SRC/packaging/arch/$p" && as_user "${mk[@]}" --packagelist | head -1)"
        if [ -f "$file" ]; then
            log "  $p: già compilato ($(basename "$file"))"
        else
            (cd "$SRC/packaging/arch/$p" && as_user "${mk[@]}" -f --nocheck --noconfirm --nodeps)
        fi
        [ -f "$file" ] || die "$p: pacchetto non prodotto ($file)."
        run pacman -U --noconfirm --needed "$file"
    done
    [ -z "$(git -C "$SRC" status --porcelain)" ] || warn "makepkg ha lasciato file in $SRC (controlla .gitignore)."

    log "Driver della rete privata (DKMS t1bridge-ncm, solo kernel 7.x, LLVM=1 automatico)"
    dkms status "t1bridge-ncm/$VER" 2>/dev/null | grep -q . && run dkms remove "t1bridge-ncm/$VER" --all >/dev/null 2>&1 || true
    run rm -rf "/usr/src/t1bridge-ncm-$VER"
    run cp -a "$REPO_DIR/dkms/t1bridge-ncm" "/usr/src/t1bridge-ncm-$VER"
    run dkms add "t1bridge-ncm/$VER"
    local k kv
    for k in /usr/lib/modules/*/; do
        kv="$(basename "$k")"; [ -d "$k/build" ] || continue
        if run dkms build "t1bridge-ncm/$VER" -k "$kv" >/dev/null 2>&1; then
            run dkms install "t1bridge-ncm/$VER" -k "$kv" --force >/dev/null && log "  installato per $kv"
        else warn "  non compilato per $kv (escluso o errore)"; fi
    done

    log "touchbar-mode aggiornato (avvia xART con la modalità display, ferma Touch ID prima della modalità tastiera)"
    run install -Dm755 "$SCRIPT_DIR/touchbar-mode.sh" /usr/local/bin/touchbar-mode

    log "Programmi in $L, CLI in $CLI, unit systemd (percorsi adattati), regole"
    for p in $BINS; do run install -Dm755 "$BUILD/$p" "$L/$p"; done
    run install -Dm755 "$BUILD/t1bridge" "$CLI"
    for p in $UNITS; do
        if [ "$DRY_RUN" = 1 ]; then echo "[dry-run] /etc/systemd/system/$p"; continue; fi
        sed -e "s#/usr/lib/t1bridge/#$L/#g" -e "s#/usr/bin/t1bridge#$CLI#g" "$SRC/systemd/$p" > "/etc/systemd/system/$p"
        chmod 644 "/etc/systemd/system/$p"
    done
    run install -Dm644 "$SRC/systemd/90-t1bridge-xart.rules" /etc/udev/rules.d/90-t1bridge-xart.rules
    run install -Dm644 "$C/49-macbookpro14-3-t1ncm.link" /etc/systemd/network/49-macbookpro14-3-t1ncm.link
    run install -Dm644 "$SRC/systemd/t1bridge.sysusers" /etc/sysusers.d/t1bridge.conf
    run install -Dm644 "$SRC/systemd/t1bridge.conf" /etc/tmpfiles.d/t1bridge.conf
    run systemd-sysusers /etc/sysusers.d/t1bridge.conf
    run systemd-tmpfiles --create /etc/tmpfiles.d/t1bridge.conf

    log "Interruttori PAM ($PAM_TOGGLE); all'inizio schermata di blocco senza impronta (limite del relay, #14)"
    run install -Dm755 "$SCRIPT_DIR/touchid-pam.sh" "$PAM_TOGGLE"
    if [ -z "$(state_get LOCKSCREEN_SET)" ]; then
        run "$PAM_TOGGLE" lockscreen off || warn "Schermata di blocco non configurata."
        state_set LOCKSCREEN_SET 1
    fi

    if ufw_active; then
        log "ufw: xART (TCP 61500) in ingresso SOLO su $IFACE e SOLO dal T1 ($PEER)"
        grep -qs '^IPV6=yes' /etc/default/ufw || warn "IPV6 non è 'yes' in /etc/default/ufw: la regola IPv6 per xART non varrà."
        run ufw_rule allow comment 'T1Bridge xART (MacBook 14,3)'
        state_set UFW 1
    else
        warn "ufw non attivo: se usi un altro firewall, apri TCP 61500 in ingresso solo su $IFACE da $PEER."
    fi

    run systemctl daemon-reload
    run udevadm control --reload
    run systemctl enable --now "${SOCKETS[@]}"

    if [ "$LIVE" = 1 ]; then
        log "Avvio la rete privata (il T1 è già in configurazione 2)"
        run modprobe apple_t1_ncm
    fi
    if [ "$DRY_RUN" = 0 ] && [ "$LIVE" = 1 ]; then
        for _ in $(seq 20); do systemctl -q is-active "t1-xart-storage@$IFACE.service" && break; sleep 0.5; done
        # Visto il 24/11/2026: la regola udev di T1Bridge non avvia xART sull'evento reale (eth0 rinominata t1ncm), anche
        # se udevadm test produce SYSTEMD_WANTS. Lo avvia touchbar-mode a ogni passaggio in display; qui lo avviamo noi.
        if [ -e "/sys/class/net/$IFACE" ] && ! systemctl -q is-active "t1-xart-storage@$IFACE.service"; then
            log "Avvio xART su $IFACE"
            systemctl start "t1-xart-storage@$IFACE.service" || warn "xART non partito: journalctl -b -u t1-ncm-ready@$IFACE -u t1-xart-storage@$IFACE"
        fi
        if ! [ -e "/sys/class/net/$IFACE" ]; then
            local n
            for n in /sys/class/net/*; do
                [ "$(basename "$(readlink "$n/device/driver" 2>/dev/null)")" = apple_t1_ncm ] || continue
                warn "La rete del T1 si chiama $(basename "$n"), non $IFACE: il file .link non è stato applicato e la"
                warn "regola ufw non la copre. Prova un riavvio; se resta così, fermati e segnala (docs/touchid-t1.md)."
            done
        elif ! systemctl -q is-active "t1-xart-storage@$IFACE.service"; then
            warn "xART non attivo su $IFACE: journalctl -b -u t1-ncm-ready@$IFACE -u t1-xart-storage@$IFACE"
        fi
    fi
    state_set INSTALLED "$T1BRIDGE_REF"
    if [ "$LIVE" = 1 ] && [ "$DRY_RUN" = 0 ] && [ -z "$(find /var/lib/t1bridge/machine-data -mindepth 1 -print -quit 2>/dev/null)" ]; then
        do_import || true   # sola lettura; se fallisce lo dice e si ferma lì
    fi
    do_status || true
    cat <<EOF

Touch ID installato. Prossimi passi (docs/touchid-t1.md):
  - Se la Touch Bar non era ancora in modalità display: spegnimento completo, riavvio, poi
      sudo scripts/install-touchid.sh import       (dati di fabbrica dal backup; se fallisce: fermati, niente recovery)
  - Registra un dito NON usato in macOS: Impostazioni di sistema > Utenti > impronte digitali (o MacBook Manager >
    Azioni > Touch ID), oppure da Konsole: fprintd-enroll -f right-index-finger. La prima registrazione può
    fallire con "prepare device keybag failed": riprova una volta.
  - Prova: fprintd-verify (o MacBook Manager > Azioni > Prova impronta).
  - sudo e schermata di blocco: MacBook Manager > Azioni > Touch ID, oppure sudo touchid-pam sudo|lockscreen on|off.
Rollback: sudo scripts/install-touchid.sh undo
EOF
}

case "$CMD" in
    lockscreen|sudo)
        [ -x "$PAM_TOGGLE" ] || die "Touch ID non installato."
        [ -n "${ONOFF:-}" ] || die "Uso: sudo scripts/install-touchid.sh $CMD on|off"
        run "$PAM_TOGGLE" "$CMD" "$ONOFF" ;;
    install) do_install ;;
    status) do_status ;;
    import) do_import ;;
    undo) do_undo ;;
esac
