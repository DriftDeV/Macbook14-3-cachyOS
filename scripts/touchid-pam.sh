#!/usr/bin/env bash
# Interruttori PAM di Touch ID sul MacBookPro14,3 (installato come /usr/local/bin/touchid-pam da install-touchid.sh).
#   touchid-pam status
#   touchid-pam lockscreen on|off   impronta nella schermata di blocco di KDE (off = /etc/pam.d/kde-fingerprint con pam_deny)
#   touchid-pam sudo on|off         impronta per sudo: "auth sufficient pam_fprintd.so max-tries=1 timeout=10" prima di
#                                   system-auth; se l'impronta non c'è, sbaglia o il servizio è fermo resta la password
# Perché la schermata di blocco è spenta di default: ogni riconoscimento consuma un'attivazione del relay della keybag e
# T1Bridge si blocca dopo ~68 per avvio (issue #14, si recupera solo con uno spegnimento completo). Vedi docs/touchid-t1.md.
# Mai in system-auth: i fallimenti finirebbero in pam_faillock (issue #57).
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Serve sudo." >&2; exit 1; }

MARK="# macbookpro14-3 touchid-pam"
SUDO_PAM=/etc/pam.d/sudo
SUDO_LINE="auth       sufficient  pam_fprintd.so max-tries=1 timeout=10"
LOCK_PAM=/etc/pam.d/kde-fingerprint

sudo_on() { grep -qF "$MARK" "$SUDO_PAM"; }
lock_ours() { grep -qsF "$MARK" "$LOCK_PAM" || grep -qsF "scripts/install-touchid.sh" "$LOCK_PAM"; }  # anche la prima versione
lock_on() { ! lock_ours; }   # spenta = c'è il nostro file con pam_deny

replace() {   # replace FILE CONTENUTO: scrittura atomica, stessi permessi
    local tmp; tmp="$(mktemp "$1.XXXXXX")"
    printf '%s\n' "$2" > "$tmp"
    chmod 644 "$tmp"; chown root:root "$tmp"
    mv -f "$tmp" "$1"
}

set_sudo() {
    [ -f /usr/lib/security/pam_fprintd.so ] || { echo "pam_fprintd.so non installato (fprintd)." >&2; exit 1; }
    local cur new
    cur="$(cat "$SUDO_PAM")"
    if [ "$1" = on ]; then
        sudo_on && { echo "sudo: impronta già attiva."; return; }
        [ -e "$SUDO_PAM.touchid-pam.bak" ] || cp -a "$SUDO_PAM" "$SUDO_PAM.touchid-pam.bak"
        # Prima della prima riga "auth": l'impronta basta da sola (sufficient), altrimenti si prosegue con la password.
        new="$(awk -v m="$MARK" -v l="$SUDO_LINE" '!done && /^[[:space:]]*-?auth[[:space:]]/ {print m; print l; done=1} {print}' <<< "$cur")"
    else
        sudo_on || { echo "sudo: impronta già spenta."; return; }
        new="$(awk -v m="$MARK" 'skip {skip=0; next} index($0, m) == 1 {skip=1; next} {print}' <<< "$cur")"
    fi
    grep -q 'system-auth' <<< "$new" || { echo "Controllo fallito: system-auth sparito, non scrivo." >&2; exit 1; }
    replace "$SUDO_PAM" "$new"
    echo "sudo: impronta $1."
}

set_lock() {
    if [ "$1" = on ]; then
        if [ -e "$LOCK_PAM" ] && ! lock_ours; then
            echo "$LOCK_PAM non è nostro: non lo tocco." >&2; exit 1
        fi
        rm -f "$LOCK_PAM"   # torna /usr/lib/pam.d/kde-fingerprint del sistema
        echo "Schermata di blocco: impronta attiva (vale dal prossimo blocco). Attenzione al limite di ~68 attivazioni per avvio."
    else
        if [ -e "$LOCK_PAM" ] && ! lock_ours; then
            echo "$LOCK_PAM non è nostro: non lo tocco." >&2; exit 1
        fi
        replace "$LOCK_PAM" "#%PAM-1.0
$MARK
# Impronta disattivata nella schermata di blocco di KDE (si sblocca con la password). Riattiva: sudo touchid-pam lockscreen on
auth       required    pam_deny.so
account    required    pam_deny.so
password   required    pam_deny.so
session    required    pam_deny.so"
        echo "Schermata di blocco: impronta spenta (password)."
    fi
}

status() {
    echo "schermata di blocco: $(lock_on && echo attiva || echo spenta)"
    echo "sudo: $(sudo_on && echo attiva || echo spenta)"
    echo "attivazioni del relay in questo avvio: $(journalctl -b --no-pager -q -u t1bridge-keybag.service 2>/dev/null | grep -c 'Started T1Bridge existing-keybag') (blocco osservato a ~68, issue #14)"
}

case "${1:-status}" in
    status) status ;;
    lockscreen) case "${2:-}" in on|off) set_lock "$2" ;; *) echo "Uso: touchid-pam lockscreen on|off" >&2; exit 2 ;; esac ;;
    sudo) case "${2:-}" in on|off) set_sudo "$2" ;; *) echo "Uso: touchid-pam sudo on|off" >&2; exit 2 ;; esac ;;
    *) echo "Uso: touchid-pam status | lockscreen on|off | sudo on|off" >&2; exit 2 ;;
esac
