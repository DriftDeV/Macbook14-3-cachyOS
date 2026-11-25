#!/usr/bin/env bash
# shellcheck shell=bash
# Funzioni comuni per gli script Linux della repo.

DRY_RUN="${DRY_RUN:-0}"
ASSUME_YES="${ASSUME_YES:-0}"
FORCE="${FORCE:-0}"

log()  { printf '\033[1;34m[*]\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m[ok]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

# Esegue un comando, oppure lo stampa soltanto con --dry-run.
run() {
    if [ "$DRY_RUN" = 1 ]; then
        printf '[dry-run] %s\n' "$*"
    else
        "$@"
    fi
}

confirm() {
    [ "$ASSUME_YES" = 1 ] && return 0
    local a
    read -r -p "$1 [y/N] " a
    [[ "$a" =~ ^[Yy]$ ]]
}

need_root() {
    [ "$DRY_RUN" = 1 ] && return 0
    [ "$(id -u)" -eq 0 ] || die "Servono i privilegi di root: rilancia con sudo."
}

# Installa un file con backup di quello esistente se diverso.
install_file() {
    local mode="$1" src="$2" dst="$3"
    if [ -e "$dst" ] && ! cmp -s "$src" "$dst"; then
        warn "$dst esiste già e differisce: salvo una copia in $dst.bak"
        run cp -a "$dst" "$dst.bak"
    fi
    run install -Dm"$mode" "$src" "$dst"
}

check_model() {
    local model
    model="$(cat /sys/class/dmi/id/product_name 2>/dev/null || true)"
    if [ "$model" != "MacBookPro14,3" ]; then
        if [ "$FORCE" = 1 ]; then
            warn "Modello rilevato: '${model:-sconosciuto}' (atteso MacBookPro14,3). Procedo per --force."
        else
            die "Modello rilevato: '${model:-sconosciuto}'. Questa repo è solo per MacBookPro14,3 (usa --force per ignorare)."
        fi
    else
        ok "Modello: $model"
    fi
}

# Restituisce i nomi dei pacchetti header per tutti i kernel installati.
kernel_header_packages() {
    local d base
    for d in /usr/lib/modules/*/; do
        [ -f "${d}pkgbase" ] || continue
        base="$(cat "${d}pkgbase")"
        echo "${base}-headers"
    done | sort -u
}

# Vero se nell'audio compare il codec Cirrus CS8409 (ID 0x10138409).
has_cs8409() {
    grep -qiE '0x10138409|CS8409' /proc/asound/card*/codec#* 2>/dev/null && return 0
    dmesg 2>/dev/null | grep -qiE 'cs8409|10138409'
}

# Desktop installato: kde (Plasma), hyprland (anche Omarchy) o other. Serve per le parti che dipendono dal desktop
# (schermata di blocco, impostazioni delle impronte, avvio automatico).
desktop_kind() {
    if pacman -Q plasma-workspace >/dev/null 2>&1; then echo kde
    elif pacman -Q hyprland >/dev/null 2>&1 || command -v Hyprland >/dev/null 2>&1; then echo hyprland
    else echo other; fi
}

# Vero su Omarchy (Arch + Hyprland di Basecamp): aggiornamenti con `omarchy update`, kernel linux-omarchy.
is_omarchy() {
    [ -d /usr/share/omarchy ] || command -v omarchy >/dev/null 2>&1 || command -v omarchy-update >/dev/null 2>&1
}

