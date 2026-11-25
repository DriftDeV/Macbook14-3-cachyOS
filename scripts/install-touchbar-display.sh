#!/usr/bin/env bash
# Installa la modalità "display" della Touch Bar T1 (grafica di T1Bridge in configurazione USB 2),
# scegliibile con touchbar-mode. Da solo non cambia modalità; install.sh poi salva "display" come predefinita
# (la modalità keyboard resta installata e serve in sospensione). Vedi docs/t1bridge.md.
#   scripts/build-t1bridge.sh                      (prima, da utente: compila i programmi T1Bridge)
#   sudo scripts/install-touchbar-display.sh       installa (non cambia modalità)
#   sudo scripts/install-touchbar-display.sh --dry-run
#   sudo scripts/install-touchbar-display.sh --undo   torna a keyboard e rimuove tutto
# Poi: sudo touchbar-mode set display   (e per tornare: sudo touchbar-mode set keyboard + spegnimento completo)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=scripts/lib.sh
source "$SCRIPT_DIR/lib.sh"
# shellcheck source=config/sources.conf
source "$REPO_DIR/config/sources.conf"

C="$REPO_DIR/config/t1bridge"
L=/usr/local/lib/macbookpro14-3/t1bridge
CONF=/etc/macbookpro14-3/touchbar.conf
SYSUNITS="macbookpro14-3-touchbar-hw.socket macbookpro14-3-touchbar-hw.service macbookpro14-3-touchbar-boot.service macbookpro14-3-touchbar-sleep.service"
USERUNITS="macbookpro14-3-touchbar-renderer.service macbookpro14-3-webcam.service"
DKMS_PKGS="t1bridge-appletbdrm t1bridge-uvc"
VER=0.1.12

UNDO=0
for a in "$@"; do
    case "$a" in
        --dry-run) DRY_RUN=1 ;;
        --undo) UNDO=1 ;;
        *) die "Opzione sconosciuta: $a" ;;
    esac
done
need_root
USER_NAME="${SUDO_USER:-}"
[ -z "$USER_NAME" ] && [ "$DRY_RUN" = 1 ] && USER_NAME="$(id -un)"
[ -n "$USER_NAME" ] && [ "$USER_NAME" != root ] || die "Lancialo con sudo dal tuo utente."
USER_HOME="$(getent passwd "$USER_NAME" | cut -d: -f6)"
USER_GROUP="$(id -gn "$USER_NAME")"
BUILD="${T1BUILD:-$USER_HOME/src/t1bridge-build}/target/release"

if [ "$UNDO" = 1 ]; then
    if [ -x /usr/local/bin/touchbar-mode ] && [ "$(cat /run/macbookpro14-3/touchbar/mode 2>/dev/null)" = display ]; then
        run /usr/local/bin/touchbar-mode keyboard || true
    fi
    run systemctl disable macbookpro14-3-touchbar-boot.service macbookpro14-3-touchbar-sleep.service 2>/dev/null || true
    run systemctl --global disable macbookpro14-3-touchbar-renderer.service 2>/dev/null || true
    for u in $SYSUNITS; do run rm -f "/etc/systemd/system/$u"; done
    for u in $USERUNITS; do run rm -f "/etc/systemd/user/$u"; done
    run rm -f /etc/udev/rules.d/99-zz-macbookpro14-3-touchbar.rules /etc/modprobe.d/macbookpro14-3-t1bridge.conf \
        /usr/local/bin/touchbar-mode /usr/local/bin/t1-webcam
    run rm -rf "$L"
    for p in $DKMS_PKGS; do
        run dkms remove "$p/$VER" --all >/dev/null 2>&1 || true
        run rm -rf "/usr/src/$p-$VER"
    done
    run systemctl daemon-reload
    run udevadm control --reload
    ok "Rimosso ($CONF lasciato). Se la Touch Bar è spenta: spegnimento completo e riaccensione."
    exit 0
fi

[ "$(cat /sys/class/dmi/id/product_name 2>/dev/null)" = MacBookPro14,3 ] || [ "${FORCE:-0}" = 1 ] || die "Solo MacBookPro14,3."
for c in dkms ffmpeg modprobe; do command -v "$c" >/dev/null || die "$c non installato."; done
modinfo v4l2loopback >/dev/null 2>&1 || warn "v4l2loopback non disponibile: niente webcam per Discord in modalità display."
# In prova (--dry-run) i programmi possono non essere ancora compilati: build-t1bridge.sh viene solo mostrato.
nobuild() { if [ "$DRY_RUN" = 1 ]; then warn "$1"; else die "$1"; fi; }
for f in t1-touchbar-hw t1-touchbar; do [ -x "$BUILD/$f" ] || nobuild "Manca $BUILD/$f: lancia prima scripts/build-t1bridge.sh (da utente)."; done
[ "$(cat "$BUILD/t1bridge-commit" 2>/dev/null)" = "$T1BRIDGE_REF" ] || nobuild "I programmi in $BUILD non sono del commit $T1BRIDGE_REF: ricompila."

log "Driver con DKMS, per ogni kernel installato (la webcam con i sorgenti uvcvideo del kernel, da kernel.org)"
for p in $DKMS_PKGS; do
    if dkms status "$p/$VER" 2>/dev/null | grep -q .; then run dkms remove "$p/$VER" --all >/dev/null 2>&1 || true; fi
    run rm -rf "/usr/src/$p-$VER"
    run cp -a "$REPO_DIR/dkms/$p" "/usr/src/$p-$VER"
    run install -m755 "$REPO_DIR/scripts/kernel-src.sh" "/usr/src/$p-$VER/kernel-src.sh"
    run dkms add "$p/$VER"
    for k in /usr/lib/modules/*/; do
        kv="$(basename "$k")"
        [ -d "$k/build" ] || continue
        if run dkms build "$p/$VER" -k "$kv" >/dev/null 2>&1; then
            run dkms install "$p/$VER" -k "$kv" --force >/dev/null && log "  $p: installato per $kv"
        else
            warn "  $p: non compilato per $kv (escluso o errore: /var/lib/dkms/$p/$VER/build/make.log)"
        fi
    done
done

log "Programmi T1Bridge ($T1BRIDGE_TAG), provider del desktop, comandi"
run install -Dm755 "$BUILD/t1-touchbar-hw" "$L/t1-touchbar-hw"
run install -Dm755 "$BUILD/t1-touchbar" "$L/t1-touchbar"
run install -Dm755 "$C/desktop-provider" "$L/desktop-provider"
run install -Dm755 "$SCRIPT_DIR/touchbar-mode.sh" /usr/local/bin/touchbar-mode
run install -Dm755 "$C/t1-webcam" /usr/local/bin/t1-webcam

log "Unit systemd, regola udev, blocco del modulo webcam"
for u in $SYSUNITS; do
    if [ "$DRY_RUN" = 1 ]; then echo "[dry-run] /etc/systemd/system/$u"; continue; fi
    sed "s/@GROUP@/$USER_GROUP/" "$C/$u" > "/etc/systemd/system/$u"
    chmod 644 "/etc/systemd/system/$u"
done
for u in $USERUNITS; do run install -Dm644 "$C/$u" "/etc/systemd/user/$u"; done
run install -Dm644 "$C/99-zz-macbookpro14-3-touchbar.rules" /etc/udev/rules.d/99-zz-macbookpro14-3-touchbar.rules
run install -Dm644 "$C/macbookpro14-3-t1bridge.modprobe.conf" /etc/modprobe.d/macbookpro14-3-t1bridge.conf
if [ ! -f "$CONF" ]; then
    run install -d "$(dirname "$CONF")"
    if [ "$DRY_RUN" = 1 ]; then echo "[dry-run] $CONF: TOUCHBAR_MODE=keyboard"; else
        printf '%s\n' '# Modalità della Touch Bar: keyboard (layout fissi, predefinita) o display (grafica T1Bridge).' \
            '# Cambia con: sudo touchbar-mode set display|keyboard' 'TOUCHBAR_MODE=keyboard' \
            "TOUCHBAR_USER=$USER_NAME" > "$CONF"
    fi
elif ! grep -q '^TOUCHBAR_USER=' "$CONF"; then
    run sh -c "echo 'TOUCHBAR_USER=$USER_NAME' >> '$CONF'"
fi
run udevadm control --reload
run systemctl daemon-reload
run systemctl enable macbookpro14-3-touchbar-boot.service macbookpro14-3-touchbar-sleep.service
run systemctl --global enable macbookpro14-3-touchbar-renderer.service
ok "Installato. Modalità attuale invariata. Per provare: sudo touchbar-mode set display"
