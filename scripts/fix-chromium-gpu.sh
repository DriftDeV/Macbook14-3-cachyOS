#!/usr/bin/env bash
# App Chromium/Electron con la GPU sulla Radeon sotto Wayland, sul MacBookPro14,3 (da utente, SENZA sudo). Vedi docs/gpu.md.
# Sotto Wayland il loro processo GPU crolla (SIGILL) appena usa i buffer "tiled" che la Radeon Polaris (radeonsi) crea
# per lo schermo; dopo tre crolli Chromium spegne l'accelerazione e disegna con la CPU. Con AMD_DEBUG=notiling, dato
# SOLO a queste app, i buffer sono lineari e non crollano più: la Radeon disegna e decodifica H.264/HEVC (il VP9 di
# YouTube lo decodifica la CPU: la Radeon non sa farlo). Niente XWayland.
#
#   scripts/fix-chromium-gpu.sh            installa: applica a tutte le app e attiva il servizio che lo riapplica
#                                          quando installi o aggiorni app (sorveglia le cartelle dei .desktop)
#   scripts/fix-chromium-gpu.sh --auto     solo applica, in silenzio (lo usa il servizio)
#   scripts/fix-chromium-gpu.sh --list     elenca le app riconosciute, senza cambiare nulla
#   scripts/fix-chromium-gpu.sh --undo     toglie tutto (servizio compreso)
#
# Come riconosce le app: il programma dell'Exec= (anche dietro uno script con "exec") sta in una cartella con
# chrome_100_percent.pak o v8_context_snapshot.bin, oppure è un runtime electron di sistema o un avviatore noto (Discord).
# Cosa scrive (sempre "env AMD_DEBUG=notiling" davanti al programma, solo per quell'app):
#   - .desktop di sistema: copia utente in ~/.local/share/applications (ha la precedenza);
#   - .desktop utente (web app/PWA di Brave e Chrome, app in ~/.local): Exec modificato;
#   - Brave e Claude Desktop, che i loro .desktop avviano per nome dal PATH: lanciatore in ~/.local/bin (viene prima di
#     /usr/bin). Claude Desktop riscrive il suo .desktop a ogni avvio; il lanciatore, ad app chiusa, riattiva anche
#     l'accelerazione se l'app l'aveva spenta da sola dopo i crolli.
# Toglie le modifiche della versione precedente (--ozone-platform=x11, cioè XWayland).
set -euo pipefail

ENVSET="AMD_DEBUG=notiling"
PREFIX="env $ENVSET"
OLDFLAG="--ozone-platform=x11"
MARK="# macbookpro14-3 fix-chromium-gpu"
CFG="${XDG_CONFIG_HOME:-$HOME/.config}"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
BIN="$HOME/.local/bin"
SELF_DIR="$HOME/.local/lib/macbookpro14-3"
SELF="$SELF_DIR/fix-chromium-gpu"
UNIT="macbookpro14-3-chromium-x11"   # nome storico del servizio
UNITDIR="$CFG/systemd/user"
SYS_APPS=/usr/share/applications
KNOWN_LAUNCHERS="/usr/share/discord/discord /opt/discord/Discord"   # avviatori che lanciano Electron da altre cartelle
WRAPPED="brave claude-desktop"                                       # avviati per nome: lanciatore in ~/.local/bin

MODE=install
case "${1:-}" in
    "") ;;
    --auto) MODE=auto ;;
    --list) MODE=list ;;
    --undo) MODE=undo ;;
    *) echo "Uso: $0 [--auto|--list|--undo]" >&2; exit 2 ;;
esac
[ "$(id -u)" -ne 0 ] || { echo "Lancialo come utente normale, non con sudo." >&2; exit 1; }

CHANGED=0
say() { [ "$MODE" = auto ] || printf '\033[1;32m[ok]\033[0m %s\n' "$*"; }
warn() { [ "$MODE" = auto ] || printf '\033[1;33m[!]\033[0m %s\n' "$*" >&2; }
write_if_changed() {   # write_if_changed FILE PERMESSI < contenuto
    local tmp; tmp="$(mktemp)"; cat > "$tmp"
    if [ -f "$1" ] && cmp -s "$tmp" "$1"; then rm -f "$tmp"; return 1; fi
    mkdir -p "$(dirname "$1")"; install -m "$2" "$tmp" "$1"; rm -f "$tmp"; CHANGED=1; return 0
}
ours() { grep -qsF "$MARK" "$1"; }

chromium_dir() { [ -f "$1/chrome_100_percent.pak" ] || [ -f "$1/v8_context_snapshot.bin" ]; }
is_chromium() {   # is_chromium PERCORSO_O_NOME [profondità]
    local p r t depth="${2:-0}"
    p="$(command -v "$1" 2>/dev/null)" || return 1
    r="$(readlink -f "$p" 2>/dev/null)" || return 1
    [ -f "$r" ] || return 1
    ours "$r" && return 0                                  # i nostri lanciatori avviano app Chromium
    chromium_dir "$(dirname "$r")" && return 0
    case " $KNOWN_LAUNCHERS " in *" $r "*) return 0 ;; esac
    case "$(basename "$r")" in electron|electron[0-9]*) return 0 ;; esac
    if [ "$depth" = 0 ] && [ "$(head -c2 "$r" 2>/dev/null)" = '#!' ]; then
        t="$(grep -oE '^[[:space:]]*exec[[:space:]]+"?/[^ "]+' "$r" | head -1 | sed -E 's/^[[:space:]]*exec[[:space:]]+"?//')"
        [ -n "$t" ] && is_chromium "$t" 1 && return 0
    fi
    return 1
}
exec_target() {   # programma dell'Exec= (salta il nostro "env AMD_DEBUG=..."); vuoto se passa da altre shell/env
    local e; e="$(sed -n 's/^Exec=//p' "$1" | head -1)"
    e="${e#"$PREFIX "}"
    e="${e#\"}"; e="${e%%[\" ]*}"
    case "$e" in env|*/env|sh|*/sh|bash|*/bash|"") return 0 ;; esac
    printf '%s\n' "$e"
}
fix_exec() {   # Exec: toglie --ozone-platform=x11 e mette "env AMD_DEBUG=notiling" davanti (una volta sola)
    sed -E -e "/^Exec=/s# $OLDFLAG( |$)#\\1#" -e "/^Exec=/{/^Exec=$PREFIX /!s#^Exec=#Exec=$PREFIX #}" "$1"
}
unfix_exec() {
    sed -E -e "s#^Exec=$PREFIX #Exec=#" -e "/^Exec=/s# $OLDFLAG( |$)#\\1#" "$1"
}
by_name() {   # vero se l'Exec avvia per nome (senza percorso) un'app con il nostro lanciatore in ~/.local/bin
    case "$1" in */*) return 1 ;; esac
    case " $WRAPPED " in *" $1 "*) return 0 ;; esac
    return 1
}
wrapper() {   # wrapper NOME: contenuto del lanciatore in ~/.local/bin
    printf '#!/bin/sh\n%s (scripts/fix-chromium-gpu.sh --undo per toglierlo)\n' "$MARK"
    printf '# Sotto Wayland il processo GPU crolla con i buffer tiled della Radeon: AMD_DEBUG=notiling solo per questa app.\n'
    if [ "$1" = claude-desktop ]; then
        cat <<'EOF'
# Ad app chiusa: riattiva l'accelerazione se l'app l'aveva spenta da sola dopo i crolli.
if ! pgrep -f '^/usr/lib/claude-desktop/claude-desktop' >/dev/null 2>&1; then
    python3 -I -c 'import json,os,sys
p=os.path.expanduser("~/.config/Claude/claude_desktop_config.json")
try: c=json.load(open(p))
except Exception: sys.exit(0)
if c.get("isHardwareAccelerationAutoDisabled"):
    c["isHardwareAccelerationDisabled"]=False; c["isHardwareAccelerationAutoDisabled"]=False
    json.dump(c,open(p,"w"),indent=2)' 2>/dev/null || true
fi
EOF
    fi
    printf 'export %s\nexec /usr/bin/%s "$@"\n' "$ENVSET" "$1"
}

do_undo() {
    systemctl --user disable --now "$UNIT.path" 2>/dev/null || true
    rm -f "$UNITDIR/$UNIT.path" "$UNITDIR/$UNIT.service" "$SELF"
    systemctl --user daemon-reload 2>/dev/null || true
    local f
    for f in "$CFG/brave-flags.conf" "$CFG"/electron*-flags.conf "$BIN/brave" "$BIN/claude-desktop"; do
        ours "$f" && rm -f "$f"
    done
    for f in "$APPS"/*.desktop; do
        [ -f "$f" ] || continue
        if ours "$f"; then rm -f "$f"
        elif grep -qsE "^Exec=($PREFIX |.* $OLDFLAG)" "$f"; then unfix_exec "$f" | write_if_changed "$f" 644 || true; fi
    done
    command -v update-desktop-database >/dev/null && update-desktop-database -q "$APPS" || true
    say "Tolto. Chiudi e riapri le app."
}

apply() {
    local f d t name w
    # Versione precedente (XWayland): brave-flags.conf ed electronNN-flags.conf scritti da noi
    for f in "$CFG/brave-flags.conf" "$CFG"/electron*-flags.conf; do
        [ -f "$f" ] || continue
        if ours "$f" || { grep -qs 'MacBookPro14,3' "$f" && ! grep -vqE '^[[:space:]]*(#|$|--ozone-platform=(x11|wayland)$)' "$f"; }; then
            rm -f "$f"; CHANGED=1; say "tolto $f (XWayland della versione precedente)"
        fi
    done
    # Lanciatori in ~/.local/bin per le app avviate per nome
    for w in $WRAPPED; do
        [ -x "/usr/bin/$w" ] || continue
        if [ -e "$BIN/$w" ] && ! ours "$BIN/$w"; then warn "$BIN/$w esiste già e non è nostro: non lo tocco."; continue; fi
        wrapper "$w" | write_if_changed "$BIN/$w" 755 && say "$w: $BIN/$w"
    done
    # .desktop di sistema -> copia utente con env
    for f in "$SYS_APPS"/*.desktop; do
        [ -f "$f" ] || continue
        name="$(basename "$f")"
        t="$(exec_target "$f")"
        if [ -z "$t" ] || ! is_chromium "$t"; then continue; fi
        by_name "$t" && continue                                         # coperta dal lanciatore
        d="$APPS/$name"
        if [ -e "$d" ] && ! ours "$d"; then continue; fi                 # copia utente non nostra: ciclo sotto
        { echo "$MARK (scripts/fix-chromium-gpu.sh --undo per toglierlo)"; fix_exec "$f"; } \
            | write_if_changed "$d" 644 && say "${name%.desktop}: $d"
    done
    # .desktop utente non nostri (web app/PWA, app in ~/.local)
    for f in "$APPS"/*.desktop; do
        [ -f "$f" ] || continue
        ours "$f" && continue
        t="$(exec_target "$f")"
        if [ -z "$t" ] || ! is_chromium "$t"; then continue; fi
        if by_name "$t"; then                                          # avviata per nome: basta il lanciatore
            unfix_exec "$f" | write_if_changed "$f" 644 || true; continue
        fi
        fix_exec "$f" | write_if_changed "$f" 644 && say "$(basename "$f" .desktop): Exec con $ENVSET"
    done
    if [ "$CHANGED" = 1 ] && command -v update-desktop-database >/dev/null; then
        update-desktop-database -q "$APPS" || true
    fi
}

do_list() {   # stato di ogni app Chromium/Electron riconosciuta
    local f t name u
    for f in "$SYS_APPS"/*.desktop "$APPS"/*.desktop; do
        [ -f "$f" ] || continue
        name="$(basename "$f")"
        u="$APPS/$name"
        [ "$f" = "$u" ] && ours "$f" && continue                        # copia nostra: contata con l'originale
        [ "$f" = "$u" ] || [ ! -f "$u" ] || ours "$u" || continue
        t="$(exec_target "$f")"; [ -n "$t" ] || continue
        is_chromium "$t" || continue
        if ours "$(command -v "$t" 2>/dev/null || echo /nonesiste)"; then echo "ok   $name (lanciatore in ~/.local/bin)"
        elif grep -qs "^Exec=$PREFIX " "$f" || ours "$u"; then echo "ok   $name"
        else echo "NO   $name ($t)"; fi
    done | sort -u
}

install_watch() {
    mkdir -p "$SELF_DIR" "$UNITDIR"
    install -m 755 "$0" "$SELF"
    cat > "$UNITDIR/$UNIT.service" <<EOF
[Unit]
Description=MacBookPro14,3: app Chromium/Electron con la GPU sulla Radeon sotto Wayland (AMD_DEBUG=notiling)

[Service]
Type=oneshot
ExecStart=$SELF --auto
EOF
    cat > "$UNITDIR/$UNIT.path" <<EOF
[Unit]
Description=MacBookPro14,3: riapplica la correzione GPU alle app Chromium/Electron nuove o aggiornate

[Path]
PathChanged=$SYS_APPS
PathChanged=$APPS
TriggerLimitIntervalSec=30
TriggerLimitBurst=4

[Install]
WantedBy=default.target
EOF
    systemctl --user daemon-reload
    systemctl --user enable --now "$UNIT.path" >/dev/null
    say "Servizio attivo: riapplica la correzione quando installi o aggiorni app ($UNIT.path)."
}

case "$MODE" in
    undo) do_undo ;;
    list) do_list ;;
    auto) apply ;;
    install)
        apply
        install_watch
        do_list
        say "Fatto. Chiudi del tutto le app Chromium/Electron (anche dall'icona nella barra di sistema) e riaprile."
        ;;
esac
