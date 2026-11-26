#!/usr/bin/env bash
# OmaBar (omarchy/omabar/ in questa repo) come renderer della Touch Bar in modalità display, accanto a T1Bridge e tiny-dfr.
# Compila il renderer, installa servizio, aggancio del tocco (stesso script di tiny-dfr), regola udev, la cartella
# /run/omabar, la sincronizzazione dei colori del tema e l'agente di sessione (finestra attiva, blocco, screensaver,
# schermi spenti, musica: omabar-agent.service).
# Non cambia il renderer in uso: dopo l'installazione si sceglie con `sudo touchbar-mode renderer omabar`
# (e si torna indietro con `sudo touchbar-mode renderer t1bridge`).
#   sudo omarchy/install-omabar.sh [--dry-run]
#   sudo omarchy/install-omabar.sh --undo        torna a t1bridge se serve e toglie tutto
# Richiede la modalità display installata (scripts/install-touchbar-display.sh) e rust.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
SCRIPTS="$REPO_DIR/scripts"
# shellcheck source=scripts/lib.sh
source "$SCRIPTS/lib.sh"

SRC="$SCRIPT_DIR/omabar"
S="$SRC/systemd"
L=/usr/local/lib/macbookpro14-3/omabar
SHARE=/usr/share/omabar
UNIT=/etc/systemd/system/macbookpro14-3-omabar.service
RULE=/etc/udev/rules.d/99-zz-macbookpro14-3-omabar.rules
DROPIN=/etc/systemd/user/macbookpro14-3-touchbar-renderer.service.d/omabar.conf
TMPFILES=/etc/tmpfiles.d/omabar.conf
SYNC=/usr/local/bin/omabar-theme-sync
AGENT=/usr/local/bin/omabar-agent
USER_UNITS=(omabar-theme-sync.service omabar-theme-sync.path omabar-agent.service)
DEPS="cairo librsvg libinput"

UNDO=0
for a in "$@"; do
    case "$a" in
        --dry-run) DRY_RUN=1 ;;
        --undo) UNDO=1 ;;
        *) die "Opzione sconosciuta: $a (--dry-run, --undo)" ;;
    esac
done
need_root
USER_NAME="${SUDO_USER:-}"
# Lanciato con pkexec (per esempio da un agente o da MacBook Manager): l'utente è quello di PKEXEC_UID.
[ -z "$USER_NAME" ] && [ -n "${PKEXEC_UID:-}" ] && USER_NAME="$(id -un "$PKEXEC_UID")"
[ -z "$USER_NAME" ] && [ "$DRY_RUN" = 1 ] && USER_NAME="$(id -un)"
[ -n "$USER_NAME" ] && [ "$USER_NAME" != root ] || die "Lancialo con sudo (o pkexec) dal tuo utente."
USER_HOME="$(getent passwd "$USER_NAME" | cut -d: -f6)"
USER_GROUP="$(id -gn "$USER_NAME")"
OUT="$USER_HOME/src/omabar-build"

as_user() {
    if [ "$DRY_RUN" = 1 ]; then echo "[dry-run] (come $USER_NAME) $*"; return 0; fi
    runuser -u "$USER_NAME" -- env HOME="$USER_HOME" PATH="/usr/local/sbin:/usr/local/bin:/usr/bin" "$@"
}
user_systemctl() {
    [ -S "/run/user/$(id -u "$USER_NAME")/systemd/private" ] || return 0   # utente non connesso
    run systemctl --user --machine="$USER_NAME@.host" "$@"
}

if [ "$UNDO" = 1 ]; then
    if command -v touchbar-mode >/dev/null && grep -qs '^TOUCHBAR_RENDERER=omabar' /etc/macbookpro14-3/touchbar.conf; then
        run touchbar-mode renderer t1bridge || warn "touchbar-mode renderer t1bridge non riuscito"
    fi
    run systemctl stop macbookpro14-3-omabar.service 2>/dev/null || true
    user_systemctl disable --now "${USER_UNITS[@]}" 2>/dev/null || true
    run systemctl --global disable "${USER_UNITS[@]}" 2>/dev/null || true
    for u in "${USER_UNITS[@]}"; do run rm -f "/etc/systemd/user/$u"; done
    run rm -f "$UNIT" "$RULE" "$DROPIN" "$TMPFILES" "$SYNC" "$AGENT"
    run rmdir --ignore-fail-on-non-empty "$(dirname "$DROPIN")" 2>/dev/null || true
    run rm -rf "$L" "$SHARE" /run/omabar
    run systemctl daemon-reload
    run udevadm control --reload
    ok "OmaBar tolto (restano /etc/omabar e la build in $OUT)."
    exit 0
fi

if ! { [ -x /usr/local/bin/touchbar-mode ] && [ -e /etc/systemd/system/macbookpro14-3-touchbar-hw.service ]; }; then
    if [ "$DRY_RUN" = 1 ]; then warn "Modalità display non ancora installata (in un'installazione vera viene prima)."
    else die "Modalità display non installata: prima sudo scripts/install-touchbar-display.sh"; fi
fi

log "Dipendenze"
miss=()
for p in $DEPS; do pacman -Q "$p" >/dev/null 2>&1 || miss+=("$p"); done
as_user sh -c 'command -v cargo' >/dev/null || miss+=(rust)
[ "${#miss[@]}" -eq 0 ] || run pacman -S --needed --noconfirm "${miss[@]}"

log "Compilazione (versioni fissate da Cargo.lock, build in $OUT)"
as_user mkdir -p "$OUT"
as_user env CARGO_TARGET_DIR="$OUT" cargo build --release --locked --manifest-path "$SRC/Cargo.toml"
BIN="$OUT/release/omabar"
[ "$DRY_RUN" = 1 ] || { [ -x "$BIN" ] && [ -x "$OUT/release/omabar-agent" ]; } || die "Compilazione non riuscita: manca $BIN o omabar-agent"

# Migrazione dal vecchio nome (CachyBar, fino al 26/11/2026): toglie binari, servizi e regole con il nome vecchio,
# sposta la configurazione personale e ricorda di ripassare a omabar se era il renderer scelto.
LEGACY_RENDERER=0
if [ -e /etc/systemd/system/macbookpro14-3-cachybar.service ] || [ -d /usr/local/lib/macbookpro14-3/cachybar ]; then
    log "Migrazione da CachyBar (nome precedente)"
    grep -qs '^TOUCHBAR_RENDERER=cachybar' /etc/macbookpro14-3/touchbar.conf && LEGACY_RENDERER=1
    run systemctl stop macbookpro14-3-cachybar.service 2>/dev/null || true
    old_units=(cachybar-theme-sync.service cachybar-theme-sync.path cachybar-agent.service)
    user_systemctl disable --now "${old_units[@]}" 2>/dev/null || true
    run systemctl --global disable "${old_units[@]}" 2>/dev/null || true
    for u in "${old_units[@]}"; do run rm -f "/etc/systemd/user/$u"; done
    run rm -f /etc/systemd/system/macbookpro14-3-cachybar.service /etc/udev/rules.d/99-zz-macbookpro14-3-cachybar.rules \
        /etc/systemd/user/macbookpro14-3-touchbar-renderer.service.d/cachybar.conf /etc/tmpfiles.d/cachybar.conf \
        /usr/local/bin/cachybar-theme-sync /usr/local/bin/cachybar-agent /run/macbookpro14-3/touchbar/cachybar
    run rm -rf /usr/local/lib/macbookpro14-3/cachybar /usr/share/cachybar /run/cachybar
    if [ -d /etc/cachybar ]; then
        run install -d -m755 /etc/omabar
        [ -e /etc/cachybar/config.toml ] && [ ! -e /etc/omabar/config.toml ] && run mv /etc/cachybar/config.toml /etc/omabar/config.toml
        run rmdir --ignore-fail-on-non-empty /etc/cachybar 2>/dev/null || true
    fi
    [ "$LEGACY_RENDERER" = 1 ] && run sed -i 's/^TOUCHBAR_RENDERER=cachybar$/TOUCHBAR_RENDERER=omabar/' /etc/macbookpro14-3/touchbar.conf
fi

log "Installazione"
run install -Dm755 "$BIN" "$L/omabar"
# Stesso aggancio del tocco di tiny-dfr (hid-multitouch con la classe della Touch Bar): è generico.
run install -Dm755 "$REPO_DIR/config/tiny-dfr/tiny-dfr-touch" "$L/touchbar-touch"
run install -Dm644 "$SRC/config.toml" "$SHARE/config.toml"
# Cartella della configurazione personale: OmaBar la guarda con inotify anche quando il file non c'è ancora.
run install -d -m755 /etc/omabar
# File personale scrivibile dall'utente: lo modifica MacBook Manager (scheda Touch Bar). Vuoto = tutto predefinito.
if [ ! -e /etc/omabar/config.toml ]; then
    if [ "$DRY_RUN" = 1 ]; then echo "[dry-run] crea /etc/omabar/config.toml (solo commenti)"
    else printf '%s\n' "# Configurazione personale di OmaBar: ogni sezione scritta qui sostituisce quella di $SHARE/config.toml." \
        "# La modifica MacBook Manager (scheda Touch Bar); OmaBar la rilegge da solo." > /etc/omabar/config.toml; fi
fi
run chgrp "$USER_GROUP" /etc/omabar/config.toml
run chmod 664 /etc/omabar/config.toml
run install -Dm755 "$S/omabar-theme-sync" "$SYNC"
run install -Dm755 "$OUT/release/omabar-agent" "$AGENT"
# touchbar-mode con la scelta del renderer omabar (stesso file di install-touchbar-display.sh e install-tiny-dfr.sh).
run install -Dm755 "$SCRIPTS/touchbar-mode.sh" /usr/local/bin/touchbar-mode
run install -Dm644 "$S/macbookpro14-3-omabar.service" "$UNIT"
# Stessa regola di tiny-dfr (sensore nel posto seat-touchbar, fuori dalla sessione grafica): un file proprio, così
# togliere uno dei due renderer non toglie la regola all'altro.
run install -Dm644 "$REPO_DIR/config/tiny-dfr/99-zz-macbookpro14-3-tiny-dfr.rules" "$RULE"
run install -Dm644 "$S/renderer-omabar.conf" "$DROPIN"
if [ "$DRY_RUN" = 1 ]; then
    echo "[dry-run] sed s/@GROUP@/$USER_GROUP/ $S/omabar.tmpfiles > $TMPFILES"
else
    sed "s/@GROUP@/$USER_GROUP/" "$S/omabar.tmpfiles" > "$TMPFILES"
    chmod 644 "$TMPFILES"
fi
run systemd-tmpfiles --create "$TMPFILES"
for u in "${USER_UNITS[@]}"; do run install -Dm644 "$S/$u" "/etc/systemd/user/$u"; done
run systemctl daemon-reload
run systemctl --global enable "${USER_UNITS[@]}"
user_systemctl daemon-reload
# restart: un agente già attivo prende il binario nuovo.
user_systemctl restart "${USER_UNITS[@]}" || warn "sincronizzazione del tema non avviata ora: partirà al prossimo accesso"
# Skill /omabar per Claude Code (personalizzare la Touch Bar da qualunque sessione), con il percorso di questa repo.
if [ -d "$USER_HOME/.claude" ]; then
    if [ "$DRY_RUN" = 1 ]; then echo "[dry-run] skill /omabar in $USER_HOME/.claude/skills/omabar"
    else
        as_user mkdir -p "$USER_HOME/.claude/skills/omabar"
        sed "s#@REPO@#$REPO_DIR#g" "$SCRIPT_DIR/claude-skill/omabar/SKILL.md" \
            | as_user tee "$USER_HOME/.claude/skills/omabar/SKILL.md" >/dev/null
    fi
fi
# Un renderer già attivo prende il binario nuovo (e crea il socket dell'agente).
if systemctl is-active --quiet macbookpro14-3-omabar.service; then run systemctl restart macbookpro14-3-omabar.service; fi
run udevadm control --reload
for d in /sys/class/input/input*; do
    [ "$(cat "$d/name" 2>/dev/null)" = "Apple Inc. iBridge Touchpad" ] || continue
    run udevadm trigger --action=change "$d"
    for e in "$d"/event*; do [ -e "$e" ] && run udevadm trigger --action=change "$e"; done
done

# Era il renderer scelto con il nome vecchio: lo riavvia con quello nuovo (se la barra è in modalità display).
[ "$LEGACY_RENDERER" = 1 ] && { run touchbar-mode renderer omabar || warn "touchbar-mode renderer omabar non riuscito"; }

ok "OmaBar installato ($L/omabar; configurazione predefinita $SHARE/config.toml, personale in /etc/omabar/config.toml)."
echo "Per usarlo:           sudo touchbar-mode renderer omabar"
echo "Misura degli FPS:     sudo touchbar-mode renderer omabar && sudo systemctl stop macbookpro14-3-omabar.service"
echo "                      sudo $L/omabar bench && sudo systemctl start macbookpro14-3-omabar.service"
echo "Per tornare indietro: sudo touchbar-mode renderer t1bridge"
