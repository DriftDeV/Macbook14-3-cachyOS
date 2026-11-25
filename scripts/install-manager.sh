#!/usr/bin/env bash
# MacBook Manager: comando `macbook-manager` (stato e azioni), GUI Qt con icona nella barra di sistema,
# helper di root autorizzato con polkit (solo azioni fisse). Vedi manager/README.md.
#   sudo scripts/install-manager.sh              installa (icona all'avvio della sessione)
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

if [ "$UNDO" = 1 ]; then
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
