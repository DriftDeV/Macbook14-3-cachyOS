#!/usr/bin/env bash
# tiny-dfr (Asahi Linux) come renderer alternativo della Touch Bar in modalità display (T1Bridge), al posto di
# t1-touchbar-hw + fnstrip. Compila il commit fissato in config/sources.conf con patches/tiny-dfr/ (sensore del T1,
# /dev/dri/touchbar, luminosità in software) e installa servizio, aggancio del tocco e regola udev.
# Non cambia il renderer in uso: dopo l'installazione si sceglie con `sudo touchbar-mode renderer tiny-dfr`
# (e si torna indietro con `sudo touchbar-mode renderer t1bridge`).
#   sudo scripts/install-tiny-dfr.sh [--dry-run]
#   sudo scripts/install-tiny-dfr.sh --undo        torna a t1bridge se serve e toglie tutto
# Richiede la modalità display installata (scripts/install-touchbar-display.sh) e rust.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=scripts/lib.sh
source "$SCRIPT_DIR/lib.sh"
# shellcheck source=config/sources.conf
source "$REPO_DIR/config/sources.conf"

C="$REPO_DIR/config/tiny-dfr"
L=/usr/local/lib/macbookpro14-3/tiny-dfr
SHARE=/usr/share/tiny-dfr
UNIT=/etc/systemd/system/macbookpro14-3-tiny-dfr.service
RULE=/etc/udev/rules.d/99-zz-macbookpro14-3-tiny-dfr.rules
DROPIN=/etc/systemd/user/macbookpro14-3-touchbar-renderer.service.d/tiny-dfr.conf
PATCH="$REPO_DIR/patches/tiny-dfr/tiny-dfr-t1.patch"
DEPS="cairo librsvg freetype2 fontconfig libinput"

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
[ -z "$USER_NAME" ] && [ "$DRY_RUN" = 1 ] && USER_NAME="$(id -un)"
[ -n "$USER_NAME" ] && [ "$USER_NAME" != root ] || die "Lancialo con sudo dal tuo utente."
USER_HOME="$(getent passwd "$USER_NAME" | cut -d: -f6)"
SRC="$USER_HOME/src/tiny-dfr"
OUT="$USER_HOME/src/tiny-dfr-build"

as_user() {
    if [ "$DRY_RUN" = 1 ]; then echo "[dry-run] (come $USER_NAME) $*"; return 0; fi
    runuser -u "$USER_NAME" -- env HOME="$USER_HOME" PATH="/usr/local/sbin:/usr/local/bin:/usr/bin" "$@"
}

if [ "$UNDO" = 1 ]; then
    if command -v touchbar-mode >/dev/null && grep -qs '^TOUCHBAR_RENDERER=tiny-dfr' /etc/macbookpro14-3/touchbar.conf; then
        run touchbar-mode renderer t1bridge || warn "touchbar-mode renderer t1bridge non riuscito"
    fi
    run systemctl stop macbookpro14-3-tiny-dfr.service 2>/dev/null || true
    run rm -f "$UNIT" "$RULE" "$DROPIN"
    run rmdir --ignore-fail-on-non-empty "$(dirname "$DROPIN")" 2>/dev/null || true
    run rm -rf "$L"
    if [ -d "$SHARE" ] && ! pacman -Qoq "$SHARE" >/dev/null 2>&1; then run rm -rf "$SHARE"; fi
    run systemctl daemon-reload
    run udevadm control --reload
    ok "tiny-dfr tolto (restano /etc/tiny-dfr, i sorgenti in $SRC e la build in $OUT)."
    exit 0
fi

if ! { [ -x /usr/local/bin/touchbar-mode ] && [ -e /etc/systemd/system/macbookpro14-3-touchbar-hw.service ]; }; then
    if [ "$DRY_RUN" = 1 ]; then warn "Modalità display non ancora installata (in un'installazione vera viene prima)."
    else die "Modalità display non installata: prima sudo scripts/install-touchbar-display.sh"; fi
fi
if pacman -Q tiny-dfr >/dev/null 2>&1; then
    die "Il pacchetto tiny-dfr è installato (usa $SHARE e /etc/tiny-dfr e parte da solo sui T2): rimuovilo prima (sudo pacman -R tiny-dfr)."
fi

log "Dipendenze"
miss=()
for p in $DEPS; do pacman -Q "$p" >/dev/null 2>&1 || miss+=("$p"); done
as_user sh -c 'command -v cargo' >/dev/null || miss+=(rust)
[ "${#miss[@]}" -eq 0 ] || run pacman -S --needed --noconfirm "${miss[@]}"

log "Sorgenti di tiny-dfr al commit ${TINYDFR_REF:0:12}"
if [ ! -d "$SRC/.git" ]; then
    as_user git clone --quiet "$TINYDFR_REPO" "$SRC"
fi
as_user git -C "$SRC" fetch --quiet origin "$TINYDFR_REF" 2>/dev/null || true
if [ "$DRY_RUN" != 1 ]; then
    as_user git -C "$SRC" cat-file -e "$TINYDFR_REF^{commit}" || die "$SRC non ha il commit $TINYDFR_REF."
fi

log "Copia pulita, patch per il T1 e compilazione (versioni fissate da Cargo.lock)"
as_user rm -rf "$OUT/src"
as_user mkdir -p "$OUT/src"
if [ "$DRY_RUN" = 1 ]; then
    echo "[dry-run] git archive $TINYDFR_REF | tar -x -C $OUT/src; patch -p1 < $PATCH"
else
    # shellcheck disable=SC2016  # argomenti posizionali della shell interna
    as_user sh -c 'git -C "$1" archive "$2" | tar -x -C "$3"' sh "$SRC" "$TINYDFR_REF" "$OUT/src"
    as_user patch -d "$OUT/src" -p1 --forward --quiet -i "$PATCH" || die "La patch non si applica al commit $TINYDFR_REF."
fi
as_user env CARGO_TARGET_DIR="$OUT/target" cargo build --release --locked --manifest-path "$OUT/src/Cargo.toml"
BIN="$OUT/target/release/tiny-dfr"
[ "$DRY_RUN" = 1 ] || [ -x "$BIN" ] || die "Compilazione non riuscita: manca $BIN"

log "Installazione"
run install -Dm755 "$BIN" "$L/tiny-dfr"
run install -Dm755 "$C/tiny-dfr-touch" "$L/tiny-dfr-touch"
# touchbar-mode con la scelta del renderer (stesso file che installa scripts/install-touchbar-display.sh).
run install -Dm755 "$SCRIPT_DIR/touchbar-mode.sh" /usr/local/bin/touchbar-mode
run install -d "$SHARE"
if [ "$DRY_RUN" = 1 ]; then
    echo "[dry-run] install -m644 $OUT/src/share/tiny-dfr/* $SHARE/"
else
    install -m644 "$OUT"/src/share/tiny-dfr/* "$SHARE/"
fi
if [ -e /etc/tiny-dfr/config.toml ]; then
    log "/etc/tiny-dfr/config.toml esiste già: lo lascio com'è"
else
    run install -Dm644 "$C/config.toml" /etc/tiny-dfr/config.toml
fi
# Scrivibile dall'utente (gruppo primario, 0664): MacBook Manager lo modifica sul posto (editor e luminosità dal vivo,
# tiny-dfr lo rilegge alla chiusura). Contiene solo etichette, icone e codici dei tasti da inviare al tocco: nessun
# comando. La cartella resta di root.
run chgrp "$(id -gn "$USER_NAME")" /etc/tiny-dfr/config.toml
run chmod 664 /etc/tiny-dfr/config.toml
run install -Dm644 "$C/macbookpro14-3-tiny-dfr.service" "$UNIT"
run install -Dm644 "$C/99-zz-macbookpro14-3-tiny-dfr.rules" "$RULE"
run install -Dm644 "$C/renderer-tiny-dfr.conf" "$DROPIN"
run systemctl daemon-reload
run udevadm control --reload
# Applica subito la regola al sensore (se la barra è in modalità display): esce dalla sessione grafica.
for d in /sys/class/input/input*; do
    [ "$(cat "$d/name" 2>/dev/null)" = "Apple Inc. iBridge Touchpad" ] || continue
    run udevadm trigger --action=change "$d"
    for e in "$d"/event*; do [ -e "$e" ] && run udevadm trigger --action=change "$e"; done
done

ok "tiny-dfr installato ($L/tiny-dfr, configurazione /etc/tiny-dfr/config.toml)."
echo "Per usarlo:        sudo touchbar-mode renderer tiny-dfr"
echo "Per tornare indietro: sudo touchbar-mode renderer t1bridge"
