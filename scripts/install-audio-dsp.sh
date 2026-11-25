#!/usr/bin/env bash
# DSP degli altoparlanti e del microfono: pacchetti pkgs/bankstown-lv2 (bassi psicoacustici di Asahi Linux) e
# pkgs/mbp143-audio (crossover tweeter/woofer, EQ, limitatori e protezione termica di Apple, con bankstown in testa),
# entrambi fissati a commit letti. Compila con makepkg come utente in ~/src/macbookpro14-3-pkgs e installa con pacman.
# Serve il driver audio (scripts/install-audio.sh). Vedi docs/audio.md.
#   sudo scripts/install-audio-dsp.sh [--dry-run]
#   sudo scripts/install-audio-dsp.sh --undo       toglie i due pacchetti (gli altoparlanti tornano senza DSP)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=scripts/lib.sh
source "$SCRIPT_DIR/lib.sh"

PKGS="bankstown-lv2 mbp143-audio"   # in quest'ordine: mbp143-audio dipende da bankstown-lv2
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
[ -n "$USER_NAME" ] && [ "$USER_NAME" != root ] || die "Lancialo con sudo dal tuo utente (makepkg non gira come root)."
USER_HOME="$(getent passwd "$USER_NAME" | cut -d: -f6)"
WORK="$USER_HOME/src/macbookpro14-3-pkgs"

as_user() {
    if [ "$DRY_RUN" = 1 ]; then echo "[dry-run] (come $USER_NAME) $*"; return 0; fi
    runuser -u "$USER_NAME" -- env HOME="$USER_HOME" PATH="/usr/local/sbin:/usr/local/bin:/usr/bin" "$@"
}

if [ "$UNDO" = 1 ]; then
    inst=""
    for p in mbp143-audio bankstown-lv2; do pacman -Q "$p" >/dev/null 2>&1 && inst="$inst $p"; done
    # shellcheck disable=SC2086
    [ -z "$inst" ] || run pacman -R --noconfirm $inst
    ok "DSP tolto. Riavvia l'audio (systemctl --user restart pipewire pipewire-pulse wireplumber) o la sessione."
    exit 0
fi

log "Dipendenze di compilazione"
miss=()
for p in base-devel git python pipewire-audio wireplumber; do pacman -Q "$p" >/dev/null 2>&1 || miss+=("$p"); done
as_user sh -c 'command -v cargo' >/dev/null || miss+=(rust)
[ "${#miss[@]}" -eq 0 ] || run pacman -S --needed --noconfirm "${miss[@]}"

FILES=()
for p in $PKGS; do
    log "Compilo $p (sorgente fissata nel PKGBUILD)"
    as_user rm -rf "$WORK/$p"
    as_user mkdir -p "$WORK/$p"
    for f in "$REPO_DIR/pkgs/$p"/*; do
        [ -f "$f" ] || continue
        case "$f" in *.pkg.tar.*) continue ;; esac
        as_user cp "$f" "$WORK/$p/"
    done
    # -d: mbp143-audio dipende da bankstown-lv2, che si installa insieme qui sotto.
    # shellcheck disable=SC2016  # argomento posizionale della shell interna
    as_user sh -c 'cd "$1" && makepkg -f -d --noconfirm' sh "$WORK/$p"
    if [ "$DRY_RUN" = 1 ]; then FILES+=("$WORK/$p/$p-*.pkg.tar.zst"); continue; fi
    f="$(find "$WORK/$p" -maxdepth 1 -name "$p-*.pkg.tar.zst" ! -name '*-debug-*' | sort | tail -1)"
    [ -n "$f" ] || die "makepkg non ha prodotto il pacchetto $p."
    FILES+=("$f")
done
run pacman -U --needed --noconfirm "${FILES[@]}"
ok "DSP degli altoparlanti installato: \"MacBook Pro 14,3 Speakers\" e \"MacBook Pro 14,3 Microphone\" al prossimo avvio."
echo "Nota: senza il driver audio caricato (dopo il riavvio) le regole non trovano la scheda e non fanno nulla."
