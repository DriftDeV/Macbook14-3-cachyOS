#!/usr/bin/env bash
# MacBook Manager: comando `macbook-manager` (stato e azioni), GUI Qt, helper di root autorizzato con polkit (solo
# azioni fisse). Vedi manager/README.md. Due versioni:
#   - CachyOS/KDE (e altri desktop): icona nella barra di sistema all'avvio della sessione;
#   - Omarchy: plugin nella barra di Omarchy (omarchy/shell-plugin/macbook-manager) al posto dell'icona.
#   sudo scripts/install-manager.sh              installa
#   sudo scripts/install-manager.sh --no-tray    senza avvio automatico dell'icona
#   sudo scripts/install-manager.sh --dry-run    mostra soltanto
#   sudo scripts/install-manager.sh --undo       rimuove
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=scripts/lib.sh
source "$SCRIPT_DIR/lib.sh"

DEST=/usr/local/lib/macbookpro14-3/manager
BIN=/usr/local/bin/macbook-manager
POLICY=/usr/share/polkit-1/actions/org.macbookpro14-3.manager.policy
APP=/usr/local/share/applications/macbook-manager.desktop
AUTOSTART=/etc/xdg/autostart/macbook-manager-tray.desktop
# Scheda Audio: script di WirePlumber che riapplica le impostazioni salvate al filtro degli altoparlanti.
WP_SCRIPT=/usr/local/share/wireplumber/scripts/macbook-manager/audio-settings.lua
WP_CONF=/etc/wireplumber/wireplumber.conf.d/92-macbook-manager-audio.conf
# Scheda Batteria: registratore (timer utente, un campione al minuto in ~/.local/share/macbook-manager/battery).
LOG_UNITS="macbook-manager-battery-log.service macbook-manager-battery-log.timer"
# Scheda GPU: comandi di root fissi (GPU dello schermo, profili della Radeon), usati dall'helper.
GPUCTL=/usr/local/lib/macbookpro14-3/gpu-control.sh
# Scheda NVRAM: suono di avvio, accensione col coperchio, voce di avvio (comandi fissi).
NVCTL=/usr/local/lib/macbookpro14-3/nvram-control.sh
# Omarchy: plugin della barra (copia di root, collegata da ~/.config/omarchy/plugins/macbook-manager).
PLUGIN=/usr/local/share/macbookpro14-3/omarchy-plugin/macbook-manager
PLUGIN_ID=macbookpro14-3.manager

TRAY=1 UNDO=0
for a in "$@"; do
    case "$a" in
        --dry-run) DRY_RUN=1 ;;
        --no-tray) TRAY=0 ;;
        --undo) UNDO=1 ;;
        *) die "Opzione sconosciuta: $a" ;;
    esac
done
need_root
OMARCHY=0; is_omarchy && OMARCHY=1
# Su Omarchy l'icona della barra di sistema la sostituisce il plugin.
[ "$OMARCHY" = 1 ] && TRAY=0
U="${SUDO_USER:-}"
[ -z "$U" ] && [ -n "${PKEXEC_UID:-}" ] && U="$(id -un "$PKEXEC_UID")"
U_HOME="$( [ -n "$U" ] && getent passwd "$U" | cut -d: -f6 || true)"
# Comando come l'utente nella sua sessione (cartelle in ~/.config, comandi di Omarchy).
as_user() {
    [ -n "$U" ] && [ "$U" != root ] || return 0
    local uid; uid="$(id -u "$U")"
    # I comandi di Omarchy vogliono OMARCHY_PATH (e il PATH) della sessione: li prendo dal suo systemd utente.
    local senv op path
    senv="$(runuser -u "$U" -- env XDG_RUNTIME_DIR="/run/user/$uid" systemctl --user show-environment 2>/dev/null || true)"
    op="$(sed -n 's/^OMARCHY_PATH=//p' <<<"$senv")"; path="$(sed -n 's/^PATH=//p' <<<"$senv")"
    run runuser -u "$U" -- env HOME="$U_HOME" XDG_RUNTIME_DIR="/run/user/$uid" \
        DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" OMARCHY_PATH="${op:-/usr/share/omarchy}" \
        PATH="${path:-/usr/local/bin:/usr/bin}" "$@"
}

# Comandi systemctl --user per l'utente che ha lanciato sudo (se c'è una sua sessione).
user_systemctl() {
    local u="${SUDO_USER:-}" uid
    [ -n "$u" ] && [ "$u" != root ] || return 0
    uid="$(id -u "$u")"
    [ -S "/run/user/$uid/bus" ] || return 0
    run runuser -u "$u" -- env XDG_RUNTIME_DIR="/run/user/$uid" \
        DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" systemctl --user "$@" || true
}

if [ "$UNDO" = 1 ]; then
    user_systemctl disable --now macbook-manager-battery-log.timer
    run systemctl --global disable macbook-manager-battery-log.timer 2>/dev/null || true
    for u in $LOG_UNITS; do run rm -f "/etc/systemd/user/$u"; done
    run rm -f "$GPUCTL" "$NVCTL"
    if [ -L "$U_HOME/.config/omarchy/plugins/macbook-manager" ]; then
        as_user omarchy plugin disable "$PLUGIN_ID" || true
        run rm -f "$U_HOME/.config/omarchy/plugins/macbook-manager"
    fi
    run rm -rf "$PLUGIN"
    run rm -rf "$DEST"
    run rm -f "$BIN" "$POLICY" "$APP" "$AUTOSTART" "$WP_SCRIPT" "$WP_CONF"
    run rmdir --ignore-fail-on-non-empty "$(dirname "$WP_SCRIPT")" 2>/dev/null || true
    ok "MacBook Manager rimosso (le impostazioni cambiate con le sue azioni restano)."
    exit 0
fi

log "Dipendenze (GUI Qt)"
run pacman -S --needed --noconfirm pyside6

log "Programma in $DEST (di root: l'helper importa solo da qui)"
run rm -rf "$DEST"
run install -d -m755 "$DEST/macbook_manager"
run install -m644 "$REPO_DIR"/manager/macbook_manager/*.py "$DEST/macbook_manager/"
run install -m755 "$REPO_DIR/manager/macbook-manager" "$REPO_DIR/manager/macbook-manager-helper" "$DEST/"
# Ottimizzazione delle app Chromium/Electron (scheda Ottimizzazione): lo script gira come utente.
run install -m755 "$REPO_DIR/scripts/fix-chromium-gpu.sh" "$DEST/fix-chromium-gpu"
run ln -sfn "$DEST/macbook-manager" "$BIN"

log "Polkit: password di amministratore solo per l'helper"
run install -Dm644 "$REPO_DIR/manager/org.macbookpro14-3.manager.policy" "$POLICY"

log "Scheda Audio: script di WirePlumber per le impostazioni del DSP degli altoparlanti"
run install -Dm644 "$REPO_DIR/config/wireplumber/macbook-manager-audio.lua" "$WP_SCRIPT"
run install -Dm644 "$REPO_DIR/config/wireplumber/92-macbook-manager-audio.conf" "$WP_CONF"

log "Scheda Batteria: registratore (timer utente, ogni minuto; i dati restano 3 mesi)"
for u in $LOG_UNITS; do run install -Dm644 "$REPO_DIR/manager/systemd/$u" "/etc/systemd/user/$u"; done
run systemctl --global enable macbook-manager-battery-log.timer
user_systemctl daemon-reload
user_systemctl enable --now macbook-manager-battery-log.timer

log "Scheda GPU: gpu-control.sh (GPU dello schermo, profili della Radeon)"
run install -Dm755 "$REPO_DIR/scripts/gpu-control.sh" "$GPUCTL"

log "Scheda NVRAM: nvram-control.sh (suono di avvio, accensione col coperchio, voce di avvio)"
run install -Dm755 "$REPO_DIR/scripts/nvram-control.sh" "$NVCTL"

if [ "$OMARCHY" = 1 ]; then
    log "Omarchy: plugin MacBook Manager nella barra (al posto dell'icona nella barra di sistema)"
    run rm -rf "$PLUGIN"
    run install -d -m755 "$PLUGIN/i18n"
    run install -m644 "$REPO_DIR"/omarchy/shell-plugin/macbook-manager/{manifest.json,Panel.qml} "$PLUGIN/"
    run install -m644 "$REPO_DIR"/omarchy/shell-plugin/macbook-manager/i18n/*.json "$PLUGIN/i18n/"
    if [ -n "$U_HOME" ]; then
        as_user mkdir -p "$U_HOME/.config/omarchy/plugins"
        as_user ln -sfn "$PLUGIN" "$U_HOME/.config/omarchy/plugins/macbook-manager"
        as_user omarchy-shell shell rescanPlugins || true
        as_user omarchy plugin enable "$PLUGIN_ID" --before omarchy.bluetooth \
            || warn "Plugin non abilitato ora (sessione di Omarchy non attiva?): omarchy plugin enable $PLUGIN_ID"
    fi
fi

log "Voce nel menu delle applicazioni"
run install -Dm644 "$REPO_DIR/manager/macbook-manager.desktop" "$APP"
if [ "$TRAY" = 1 ]; then
    log "Icona nella barra di sistema all'avvio della sessione"
    run install -Dm644 "$REPO_DIR/manager/macbook-manager-tray.desktop" "$AUTOSTART"
else
    run rm -f "$AUTOSTART"
fi
command -v update-desktop-database >/dev/null && run update-desktop-database -q /usr/local/share/applications || true

# Un manager già aperto (anche solo come icona nella barra di sistema) userebbe ancora il codice vecchio: riaprendolo
# dal menu tornerebbe in primo piano quello. Lo chiudo.
if [ "$DRY_RUN" != 1 ] && pgrep -f '/usr/local/bin/macbook-manager gui' >/dev/null 2>&1; then
    pkill -f '/usr/local/bin/macbook-manager gui' || true
    warn "Il manager aperto è stato chiuso per caricare la versione nuova: riaprilo dal menu."
fi
ok "Installato. Apri \"MacBook Manager\" dal menu, oppure: macbook-manager status"
echo "Le impostazioni audio salvate vengono riapplicate da WirePlumber dal prossimo accesso (o dopo:"
echo "  systemctl --user restart wireplumber)."
