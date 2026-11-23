#!/usr/bin/env bash
# Compila (da utente, NON con sudo) i programmi Touch Bar di T1Bridge per la modalità display:
# t1-touchbar-hw (servizio: display, tocco, tasti) e t1-touchbar (renderer). Sorgente fissato in
# config/sources.conf; risultato in ~/src/t1bridge-build/target/release. Serve rust (pacman -S rust).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=scripts/lib.sh
source "$SCRIPT_DIR/lib.sh"
# shellcheck source=config/sources.conf
source "$REPO_DIR/config/sources.conf"
[ "$(id -u)" -ne 0 ] || die "Lancialo da utente normale (cargo non va eseguito come root)."
command -v cargo >/dev/null || die "cargo non trovato: sudo pacman -S rust"

SRC="${T1BRIDGE_SRC:-$HOME/src/t1bridge}"
OUT="${T1BUILD:-$HOME/src/t1bridge-build}"
if [ ! -d "$SRC/.git" ]; then
    log "Clono $T1BRIDGE_REPO ($T1BRIDGE_TAG) in $SRC"
    git clone --quiet --depth 1 --branch "$T1BRIDGE_TAG" "$T1BRIDGE_REPO" "$SRC"
fi
[ "$(git -C "$SRC" rev-parse HEAD)" = "$T1BRIDGE_REF" ] \
    || die "$SRC non è al commit $T1BRIDGE_REF: controlla o cancella la cartella e rilancia."
[ -z "$(git -C "$SRC" status --porcelain)" ] || die "$SRC ha modifiche locali: mi fermo."

log "Compilo t1-touchbar-hw e t1-touchbar (versioni fissate da Cargo.lock)"
(cd "$SRC" && CARGO_TARGET_DIR="$OUT/target" cargo build --release --locked \
    -p t1-touchbar-hw -p t1-touchbar --features t1-touchbar-hw/service)
echo "$T1BRIDGE_REF" > "$OUT/target/release/t1bridge-commit"
ok "Pronti in $OUT/target/release. Poi: sudo scripts/install-touchbar-display.sh"
