#!/usr/bin/env bash
# Modalità della Touch Bar del MacBookPro14,3 (installato come /usr/local/bin/touchbar-mode):
#   keyboard  configurazione USB 1 del T1: lo stack della repo (apple-ibridge, apple-ib-tb, apple-ib-als),
#             layout fissi, webcam con uvcvideo del kernel. Predefinita, provata, sicura.
#   display   configurazione USB 2: grafica di T1Bridge (appletbdrm T1, t1-touchbar-hw, renderer),
#             webcam H.264 con uvcvideo_t1 (+ webcam virtuale per Discord: t1-webcam on).
# Comandi (root):
#   touchbar-mode status
#   touchbar-mode set display            salva la scelta in /etc/macbookpro14-3/touchbar.conf e la applica subito
#   touchbar-mode set keyboard           salva la scelta; dalla modalità display vale dal prossimo spegnimento completo
#                                        (la grafica resta attiva fino ad allora: niente barra spenta)
#   touchbar-mode display|keyboard       applica subito, senza salvare
#   touchbar-mode boot                   (servizio all'avvio) applica la scelta salvata
#   touchbar-mode sleep-pre|sleep-post   (servizio di sospensione) keyboard prima dello sleep, display dopo
#   touchbar-mode renderer [t1bridge|tiny-dfr]   mostra o sceglie il renderer della modalità display (salvato; se la
#                                        barra è in modalità display cambia subito):
#                                        t1bridge  t1-touchbar-hw + renderer utente (fnstrip o quello di T1Bridge)
#                                        tiny-dfr  tiny-dfr di Asahi Linux (scripts/install-tiny-dfr.sh)
# Tornando a keyboard senza riavvio la barra resta spenta (il tocco funziona): il lato display del T1 resta nello
# stato della configurazione 2 e si azzera solo con uno spegnimento completo (~30 s). Provati senza successo il
# 23/11/2026: porta USB disattivata/riattivata, reset USB, sospensione S3 (il T1 non perde corrente). L'unico reset
# software noto (ACPI FRST) manda il T1 in recovery: non usarlo. Vedi docs/t1bridge.md.
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Serve sudo." >&2; exit 1; }

L=/usr/local/lib/macbookpro14-3/t1bridge
CONF=/etc/macbookpro14-3/touchbar.conf
STATE=/run/macbookpro14-3/touchbar
TOUCHBAR_MODE=keyboard
TOUCHBAR_RENDERER=t1bridge
TOUCHBAR_USER=""
# shellcheck source=/dev/null
[ -r "$CONF" ] && . "$CONF"
SLEEP_CALL=0

log() { echo "== $*"; logger -t touchbar-mode "$*" 2>/dev/null || true; }
mod_loaded() { [ -d "/sys/module/$1" ]; }
user_systemctl() {
    [ -n "$TOUCHBAR_USER" ] || return 0
    [ -S "/run/user/$(id -u "$TOUCHBAR_USER" 2>/dev/null)/systemd/private" ] || return 0   # utente non connesso
    systemctl --user --machine="$TOUCHBAR_USER@.host" "$@"
}
t1_usb() {
    local d
    for d in /sys/bus/usb/devices/*; do
        [ "$(cat "$d/idVendor" 2>/dev/null)" = 05ac ] && [ "$(cat "$d/idProduct" 2>/dev/null)" = 8600 ] && { echo "$d"; return 0; }
    done
    return 1
}
current_mode() { cat "$STATE/mode" 2>/dev/null || echo keyboard; }
TDFR_UNIT=macbookpro14-3-tiny-dfr.service
tdfr_installed() { [ -e "/etc/systemd/system/$TDFR_UNIT" ] && [ -x /usr/local/lib/macbookpro14-3/tiny-dfr/tiny-dfr ]; }
renderer_wanted() {
    if [ "$TOUCHBAR_RENDERER" = tiny-dfr ]; then
        tdfr_installed && { echo tiny-dfr; return; }
        log "renderer tiny-dfr scelto ma non installato (scripts/install-tiny-dfr.sh): uso t1bridge"
    fi
    echo t1bridge
}

# Avvia il renderer scelto sullo schermo della barra già pronto (dev-dri-touchbar.device attivo).
start_renderer() {
    if [ "$(renderer_wanted)" = tiny-dfr ]; then
        touch "$STATE/tiny-dfr"   # il drop-in del renderer utente non lo fa partire
        user_systemctl stop macbookpro14-3-touchbar-renderer.service 2>/dev/null || true
        systemctl stop macbookpro14-3-touchbar-hw.service macbookpro14-3-touchbar-hw.socket 2>/dev/null || true
        systemctl start "$TDFR_UNIT" || { log "tiny-dfr non avviato (journalctl -u $TDFR_UNIT)"; return 1; }
        log "renderer: tiny-dfr"
    else
        rm -f "$STATE/tiny-dfr"
        systemctl stop "$TDFR_UNIT" 2>/dev/null || true
        systemctl start macbookpro14-3-touchbar-hw.socket macbookpro14-3-touchbar-hw.service
        user_systemctl start macbookpro14-3-touchbar-renderer.service || log "renderer non avviato"
        log "renderer: t1bridge"
    fi
}

# Touch ID (scripts/install-touchid.sh): la rete privata del T1 (t1ncm) nasce con la configurazione 2. La regola udev di
# T1Bridge non avvia xART sull'evento reale (eth0 rinominata t1ncm, visto il 24/11/2026): lo avviamo noi appena compare
# l'interfaccia, in parallelo all'attesa dello schermo della barra, senza bloccare avvio e risveglio. Il relay della
# keybag parte con xART (Wants). La schermata di blocco di KDE riprova l'impronta ogni ~3 s finché Touch ID è pronto.
touchid_installed() { [ -e /etc/systemd/system/t1-xart-storage@.service ]; }
touchid_kick() {
    [ "${TID_STARTED:-0}" = 0 ] && touchid_installed && [ -e /sys/class/net/t1ncm ] || return 0
    if systemctl start --no-block t1-xart-storage@t1ncm.service; then
        TID_STARTED=1; log "Touch ID: avvio xART su t1ncm"
    else
        TID_STARTED=1; log "Touch ID: xART non avviato"
    fi
    return 0
}

to_display() {
    local usb card c
    usb="$(t1_usb)" || { log "T1 (05ac:8600) non trovato (05ac:1281 = recovery: spegnimento completo)"; return 1; }
    if ! [ -x "$L/t1-touchbar-hw" ] || ! modinfo appletbdrm 2>/dev/null | grep -q 'p8600'; then
        log "modalità display non installata per $(uname -r) (DKMS t1bridge-appletbdrm?): resto in keyboard"
        return 1
    fi
    install -d -m755 "$STATE"

    log "display: blocco i moduli della modalità tastiera fino al riavvio"
    systemctl stop iio-sensor-proxy.service 2>/dev/null || true
    systemctl mask --runtime iio-sensor-proxy.service >/dev/null 2>&1 || true
    install -d /run/modprobe.d
    printf '%s\n' '# touchbar-mode display: sparisce al riavvio.' 'install apple_ibridge /usr/bin/true' \
        'install apple_ib_tb /usr/bin/true' 'install apple_ib_als /usr/bin/true' > /run/modprobe.d/macbookpro14-3-touchbar.conf
    sleep 1
    for m in apple_ib_als apple_ib_tb apple_ibridge; do mod_loaded "$m" && rmmod "$m"; done

    log "display: driver display T1 e webcam H.264"
    modprobe appletbdrm
    if modinfo uvcvideo_t1 >/dev/null 2>&1 && ! mod_loaded uvcvideo_t1; then
        if ! mod_loaded uvcvideo || rmmod uvcvideo 2>/dev/null; then
            modprobe uvcvideo_t1 || log "uvcvideo_t1 non caricato: niente webcam in modalità display"
        else
            log "webcam in uso (uvcvideo occupato): niente webcam in modalità display"
        fi
    fi
    if ! mod_loaded v4l2loopback; then
        modprobe v4l2loopback devices=1 video_nr=10 card_label="T1 camera (Discord)" exclusive_caps=1 \
            && touch "$STATE/v4l2loopback"
    fi

    log "display: T1 in configurazione 2"
    [ "$(cat "$usb/bConfigurationValue")" = 2 ] || echo 2 > "$usb/bConfigurationValue"
    card=""
    TID_STARTED=0
    for _ in $(seq 40); do
        touchid_kick
        for c in /sys/class/drm/card*; do
            [ "$(basename "$(readlink "$c/device/driver" 2>/dev/null)")" = appletbdrm ] && card="$c" && break 2
        done
        sleep 0.25
    done
    [ -n "$card" ] || { log "display: schermo della Touch Bar non comparso (dmesg)"; return 1; }
    # Il servizio dipende da dev-dri-touchbar.device, che systemd conosce solo se l'ultimo evento udev
    # dello schermo è passato dalla nostra regola (TAG+="systemd"): rielabora l'evento (come un rebind)
    # e aspetta il dispositivo, invece di restare appeso sull'avvio del servizio.
    # Niente "udevadm settle": al risveglio udev resta occupato con le altre interfacce del T1 e settle arrivava al
    # limite di 10 s (24/11/2026); si aspetta solo il dispositivo che serve.
    udevadm trigger --action=change "$card"
    for _ in $(seq 60); do
        touchid_kick
        systemctl -q is-active dev-dri-touchbar.device && break
        sleep 0.25
    done
    systemctl -q is-active dev-dri-touchbar.device \
        || { log "display: systemd non vede /dev/dri/touchbar (regola udev installata?)"; return 1; }
    # Sensore di luce: in configurazione 2 lo espone hid_sensor_als (driver del kernel).
    systemctl unmask --runtime iio-sensor-proxy.service >/dev/null 2>&1 || true
    systemctl start iio-sensor-proxy.service 2>/dev/null || true
    if touchid_installed && [ "$TID_STARTED" = 0 ]; then
        for _ in $(seq 20); do touchid_kick; [ "$TID_STARTED" = 1 ] && break; sleep 0.25; done
        [ "$TID_STARTED" = 1 ] || log "Touch ID: rete t1ncm non comparsa (modulo apple_t1_ncm?)"
    fi
    echo display > "$STATE/mode"
    touch "$STATE/display" "$STATE/display-this-boot"   # il secondo resta fino al riavvio (barra spenta in keyboard)
    start_renderer || true
    log "display: attiva ($(basename "$card"))"
}

to_keyboard() {
    local usb
    usb="$(t1_usb)" || { log "T1 (05ac:8600) non trovato"; return 1; }
    log "keyboard: fermo renderer, webcam virtuale e servizio Touch Bar"
    rm -f "$STATE/display"
    # Touch ID (scripts/install-touchid.sh): broker e relay della keybag si fermano in modo pulito prima che la
    # configurazione 1 tolga rete privata e Secure Enclave; xART si ferma da solo con l'interfaccia (BindsTo) e al
    # ritorno in configurazione 2 udev lo riavvia, insieme al relay.
    if [ -e /etc/systemd/system/t1-touchid-auth.service ]; then
        systemctl stop t1-touchid-auth.service t1bridge-keybag.service 2>/dev/null || true
    fi
    user_systemctl stop macbookpro14-3-touchbar-renderer.service macbookpro14-3-webcam.service 2>/dev/null || true
    systemctl stop "$TDFR_UNIT" macbookpro14-3-touchbar-hw.service macbookpro14-3-touchbar-hw.socket 2>/dev/null || true
    mod_loaded appletbdrm && rmmod appletbdrm
    # uvcvideo_t1 gestisce anche la configurazione 1: se un programma tiene aperta la webcam lo si lascia
    # caricato (scaricarlo fallirebbe e uvcvideo non potrebbe registrarsi con lo stesso nome).
    if mod_loaded uvcvideo_t1 && ! rmmod uvcvideo_t1 2>/dev/null; then
        log "keyboard: webcam in uso, uvcvideo_t1 resta caricato (funziona anche in configurazione 1)"
    fi
    if [ -e "$STATE/v4l2loopback" ] && [ "$SLEEP_CALL" = 0 ]; then
        rmmod v4l2loopback 2>/dev/null && rm -f "$STATE/v4l2loopback"
    fi
    rm -f /run/modprobe.d/macbookpro14-3-touchbar.conf

    log "keyboard: T1 in configurazione 1 e stack della repo"
    [ "$(cat "$usb/bConfigurationValue")" = 1 ] || echo 1 > "$usb/bConfigurationValue"
    sleep 1
    mod_loaded uvcvideo || mod_loaded uvcvideo_t1 || modprobe uvcvideo
    modprobe apple_ibridge && modprobe apple_ib_tb && modprobe apple_ib_als
    systemctl unmask --runtime iio-sensor-proxy.service >/dev/null 2>&1 || true
    systemctl start iio-sensor-proxy.service 2>/dev/null || true
    sleep 2
    install -d -m755 "$STATE"
    echo keyboard > "$STATE/mode"
    log "keyboard: attiva (configurazione $(cat "$usb/bConfigurationValue"))"
}

status() {
    local usb
    usb="$(t1_usb)" || { echo "T1 non trovato"; return 0; }
    echo "scelta salvata: $TOUCHBAR_MODE   attuale: $(current_mode)   configurazione USB: $(cat "$usb/bConfigurationValue")"
    printf '  moduli:'; for m in apple_ibridge apple_ib_tb apple_ib_als appletbdrm uvcvideo uvcvideo_t1 v4l2loopback; do
        mod_loaded "$m" && printf ' %s' "$m"; done; echo
    echo "  renderer scelto: $TOUCHBAR_RENDERER$(tdfr_installed || echo ' (tiny-dfr non installato)')   tiny-dfr: $(systemctl is-active "$TDFR_UNIT" 2>/dev/null)"
    echo "  servizio Touch Bar: $(systemctl is-active macbookpro14-3-touchbar-hw.service 2>/dev/null)   renderer: $(user_systemctl is-active macbookpro14-3-touchbar-renderer.service 2>/dev/null)"
    echo "  webcam: $(printf '%s ' /dev/video*)  webcam virtuale: $(user_systemctl is-active macbookpro14-3-webcam.service 2>/dev/null)"
}

save_conf() {   # chiave valore
    install -d -m755 "$(dirname "$CONF")"
    if [ -f "$CONF" ] && grep -q "^$1=" "$CONF"; then
        sed -i "s/^$1=.*/$1=$2/" "$CONF"
    else
        echo "$1=$2" >> "$CONF"
    fi
}
save_mode() { save_conf TOUCHBAR_MODE "$1"; }

case "${1:-status}" in
    status) status ;;
    display) to_display ;;
    keyboard) to_keyboard ;;
    set)
        case "${2:-}" in
            display) save_mode display; to_display ;;
            keyboard) save_mode keyboard
                if [ "$(current_mode)" = display ]; then
                    log "keyboard salvata: la grafica resta fino allo spegnimento completo (solo così il T1 riparte pulito)"
                    echo "Spegni il Mac, aspetta ~30 s e riaccendi: partirà in modalità tastiera."
                    echo "(Per passare subito, con la barra spenta ma il tocco funzionante: sudo touchbar-mode keyboard)"
                fi ;;
            *) echo "Uso: touchbar-mode set display|keyboard" >&2; exit 1 ;;
        esac ;;
    renderer)
        case "${2:-}" in
            "") echo "$TOUCHBAR_RENDERER" ;;
            t1bridge|tiny-dfr)
                [ "$2" = tiny-dfr ] && ! tdfr_installed && { echo "tiny-dfr non installato: sudo scripts/install-tiny-dfr.sh" >&2; exit 1; }
                save_conf TOUCHBAR_RENDERER "$2"; TOUCHBAR_RENDERER="$2"
                if [ "$(current_mode)" = display ]; then
                    start_renderer
                else
                    log "renderer $2 salvato: vale dalla prossima attivazione della modalità display"
                fi ;;
            *) echo "Uso: touchbar-mode renderer [t1bridge|tiny-dfr]" >&2; exit 1 ;;
        esac ;;
    boot) [ "$TOUCHBAR_MODE" = display ] && { to_display || log "boot: modalità display non riuscita, resto in keyboard"; }; exit 0 ;;
    sleep-pre)
        if [ "$(current_mode)" = display ]; then
            SLEEP_CALL=1; touch "$STATE/resume-display"; to_keyboard || true
        fi ;;
    sleep-post)
        if [ -e "$STATE/resume-display" ]; then
            rm -f "$STATE/resume-display"; SLEEP_CALL=1; to_display || log "risveglio: modalità display non riuscita"
        fi ;;
    *) echo "Uso: touchbar-mode status|set display|set keyboard|display|keyboard|renderer [t1bridge|tiny-dfr]" >&2; exit 1 ;;
esac
