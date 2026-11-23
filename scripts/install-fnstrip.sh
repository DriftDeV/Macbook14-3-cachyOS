#!/usr/bin/env bash
# Installa (da utente, NON con sudo) fnstrip come renderer della Touch Bar in modalità display:
# temi, cursori, riga "extra" con grafici (doppio tocco su Fn). Configurazione: ~/.config/fnstrip/config.toml
# (i pulsanti personali eseguono comandi: scrivili tu). Serve rust e brightnessctl.
#   scripts/install-fnstrip.sh          compila, installa in ~/.local/bin e lo seleziona
#   scripts/install-fnstrip.sh --undo   torna al renderer incluso di T1Bridge
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=scripts/lib.sh
source "$SCRIPT_DIR/lib.sh"
# shellcheck source=config/sources.conf
source "$REPO_DIR/config/sources.conf"
[ "$(id -u)" -ne 0 ] || die "Lancialo da utente normale, non con sudo."

SEL="${XDG_CONFIG_HOME:-$HOME/.config}/t1bridge/renderer"
restart_renderer() {
    local u
    for u in macbookpro14-3-touchbar-renderer.service t1test-touchbar.service; do
        systemctl --user -q is-active "$u" 2>/dev/null && systemctl --user restart "$u" && log "riavviato $u"
    done
    return 0
}

if [ "${1:-}" = --undo ]; then
    rm -f "$SEL"
    restart_renderer
    ok "Tolto il collegamento: torna il renderer incluso (~/.local/bin/fnstrip e la sua configurazione restano)."
    exit 0
fi

command -v cargo >/dev/null || die "cargo non trovato: sudo pacman -S rust"
command -v brightnessctl >/dev/null || warn "brightnessctl manca: cursori di luminosità e tastiera non funzioneranno (sudo pacman -S brightnessctl)."
SRC="$HOME/src/fnstrip"
if [ ! -d "$SRC/.git" ]; then
    git clone --quiet "$FNSTRIP_REPO" "$SRC"
fi
git -C "$SRC" fetch --quiet origin "$FNSTRIP_REF" 2>/dev/null || true
git -C "$SRC" checkout --quiet "$FNSTRIP_REF"
[ "$(git -C "$SRC" rev-parse HEAD)" = "$FNSTRIP_REF" ] || die "fnstrip non è al commit $FNSTRIP_REF."
[ -z "$(git -C "$SRC" status --porcelain)" ] || die "$SRC ha modifiche locali: mi fermo."
grep -q "#$T1BRIDGE_REF" "$SRC/Cargo.lock" || die "Cargo.lock di fnstrip non punta a T1Bridge $T1BRIDGE_REF."

log "Compilo fnstrip (versioni fissate da Cargo.lock)"
(cd "$SRC" && CARGO_TARGET_DIR="$HOME/src/fnstrip-build" cargo build --release --locked)
install -Dm755 "$HOME/src/fnstrip-build/release/fnstrip" "$HOME/.local/bin/fnstrip"
CFG="${XDG_CONFIG_HOME:-$HOME/.config}/fnstrip/config.toml"
[ -e "$CFG" ] || install -Dm644 "$SRC/config/default.toml" "$CFG"
install -d "$(dirname "$SEL")"
ln -sfn "$HOME/.local/bin/fnstrip" "$SEL"
restart_renderer
ok "fnstrip selezionato ($("$HOME/.local/bin/fnstrip" --version)). Configurazione: $CFG"
