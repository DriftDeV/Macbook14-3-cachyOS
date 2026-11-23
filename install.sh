#!/usr/bin/env bash
# Installazione del supporto hardware per MacBookPro14,3 su CachyOS/Arch.
# Da lanciare DOPO aver installato CachyOS. Provalo prima con --dry-run.
set -euo pipefail
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib.sh
source "$REPO_DIR/scripts/lib.sh"

DO_TOUCHBAR=1 DO_AUDIO=1 DO_SLEEP=1 DO_INITRAMFS=1 DO_BACKUP=1
WIFI_FILE=""

usage() {
    cat <<EOF
Uso: sudo ./install.sh [opzioni]
  --dry-run            mostra cosa verrebbe fatto, senza modificare nulla
  --yes                non chiedere conferme
  --force              ignora il controllo del modello (sconsigliato)
  --wifi-nvram FILE    installa il file NVRAM del BCM43602 (vedi docs)
  --skip-backup        non fare il backup dell'ESP (sconsigliato: contiene il firmware T1)
  --skip-touchbar | --skip-audio | --skip-sleep | --skip-initramfs
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=1 ;;
        --yes) ASSUME_YES=1 ;;
        --force) FORCE=1 ;;
        --wifi-nvram) WIFI_FILE="${2:-}"; shift ;;
        --skip-backup) DO_BACKUP=0 ;;
        --skip-touchbar) DO_TOUCHBAR=0 ;;
        --skip-audio) DO_AUDIO=0 ;;
        --skip-sleep) DO_SLEEP=0 ;;
        --skip-initramfs) DO_INITRAMFS=0 ;;
        -h|--help) usage; exit 0 ;;
        *) usage; die "Opzione sconosciuta: $1" ;;
    esac
    shift
done
export DRY_RUN ASSUME_YES FORCE

check_model
command -v pacman >/dev/null || die "pacman non trovato: serve un sistema Arch/CachyOS."
need_root
FAILED=""

step() { log "== $* =="; }

if [ "$DO_BACKUP" = 1 ]; then
    step "Backup ESP e firmware T1"
    bash "$REPO_DIR/scripts/backup-esp.sh" || die "Backup fallito: mi fermo."
fi

step "Pacchetti di base"
HEADERS="$(kernel_header_packages | tr '\n' ' ')"
[ -n "$HEADERS" ] || warn "Nessun pacchetto header individuato: i moduli DKMS non compileranno."
# shellcheck disable=SC2086
run pacman -S --needed --noconfirm base-devel dkms git iio-sensor-proxy linux-firmware $HEADERS

step "Configurazione"
install_file 644 "$REPO_DIR/config/libinput/local-overrides.quirks" /etc/libinput/local-overrides.quirks
if [ "$DO_INITRAMFS" = 1 ]; then
    install_file 644 "$REPO_DIR/config/mkinitcpio/macbookpro14-3.conf" /etc/mkinitcpio.conf.d/macbookpro14-3.conf
fi
if [ "$DO_SLEEP" = 1 ]; then
    step "Sospensione"
    if [ "$DRY_RUN" = 1 ]; then
        bash "$REPO_DIR/scripts/install-sleep.sh" --dry-run
    else
        bash "$REPO_DIR/scripts/install-sleep.sh" || FAILED="$FAILED sleep"
    fi
fi

if [ -n "$WIFI_FILE" ]; then
    step "Wi-Fi NVRAM"
    bash "$REPO_DIR/scripts/install-wifi-nvram.sh" --file "$WIFI_FILE" || FAILED="$FAILED wifi"
else
    warn "Wi-Fi: nessun --wifi-nvram dato. Senza il file NVRAM resta solo il 2,4 GHz."
fi

if [ "$DO_TOUCHBAR" = 1 ]; then
    step "Touch Bar T1"
    if [ "$DRY_RUN" = 1 ]; then
        bash "$REPO_DIR/scripts/install-touchbar.sh" --dry-run
    else
        bash "$REPO_DIR/scripts/install-touchbar.sh" || FAILED="$FAILED touchbar"
    fi
fi

if [ "$DO_AUDIO" = 1 ]; then
    step "Audio CS8409"
    if [ "$DRY_RUN" = 1 ]; then
        bash "$REPO_DIR/scripts/install-audio.sh" --dry-run
    else
        bash "$REPO_DIR/scripts/install-audio.sh" || FAILED="$FAILED audio"
    fi
fi

if [ "$DO_INITRAMFS" = 1 ]; then
    step "Rigenero initramfs"
    run mkinitcpio -P
fi

echo
if [ -n "$FAILED" ]; then
    warn "Componenti non installati:$FAILED (il resto è stato applicato)."
    exit 2
fi
ok "Fatto. Riavvia, poi verifica:"
cat <<'EOF'
  zgrep -E 'APPLESPI|SPI_PXA2XX' /proc/config.gz    # supporto tastiera nel kernel
  dkms status
  journalctl -k | grep -iE 'cs8409|brcmfmac|apple.?ib'
EOF
