#!/usr/bin/env bash
# Wi-Fi BCM43602 del MacBookPro14,3: 5 GHz, segnale pieno, canali a 80 MHz.
#
# Genera il file NVRAM dalla calibrazione di fabbrica del chip di questo Mac (SROM) e scrive
# il firmware di linux-firmware con la tabella front-end Apple (dnlbtz/mbp143-wifi, vedi
# config/sources.conf), più la configurazione di NetworkManager. Il Wi-Fi cade per ~20 s.
#   sudo scripts/install-wifi.sh            installa
#   sudo scripts/install-wifi.sh --dry-run  mostra soltanto
#   sudo scripts/install-wifi.sh --undo     rimuove (torna a linux-firmware senza NVRAM)
# Alternativa con un file NVRAM già in tuo possesso: scripts/install-wifi-nvram.sh --file.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=scripts/lib.sh
source "$SCRIPT_DIR/lib.sh"
# shellcheck source=config/sources.conf
source "$REPO_DIR/config/sources.conf"

SHARE=/usr/share/macbookpro14-3/wifi
SETUP="$SHARE/mbp143-wifi-setup"
NMCONF=/etc/NetworkManager/conf.d/90-macbookpro14-3-wifi.conf
NMDISP=/etc/NetworkManager/dispatcher.d/91-macbookpro14-3-wifi-prefer-5ghz
FW=/usr/lib/firmware/brcm/brcmfmac43602-pcie.bin

UNDO=0
for a in "$@"; do
    case "$a" in
        --dry-run) DRY_RUN=1 ;;
        --undo) UNDO=1 ;;
        *) die "Opzione sconosciuta: $a" ;;
    esac
done
need_root

if [ "$UNDO" = 1 ]; then
    if [ -f "$SETUP" ]; then run env MBP143_WIFI_SHARE="$SHARE" python3 -I "$SETUP" remove; fi
    run rm -rf "$SHARE"
    run rm -f "$NMCONF" "$NMDISP"
    run nmcli general reload conf || true
    ok "Rimosso: il chip torna al firmware di linux-firmware senza file NVRAM (solo 2,4 GHz)."
    exit 0
fi

[ "$(cat /sys/class/dmi/id/product_name 2>/dev/null)" = MacBookPro14,3 ] || [ "${FORCE:-0}" = 1 ] \
    || die "Solo per MacBookPro14,3: template e tabella front-end sono di questa scheda."
grep -qx 0x43ba /sys/bus/pci/devices/*/device 2>/dev/null || die "Nessun BCM43602 (14e4:43ba) trovato."
for c in python3 curl zstd sha256sum modprobe nmcli; do
    command -v "$c" >/dev/null || die "$c non installato."
done
for f in "$FW" "$FW.zst" "$FW.xz"; do [ -e "$f" ] && break; done
[ -e "$f" ] || die "Firmware $FW non trovato: installa linux-firmware-broadcom."

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
log "Scarico i file di mbp143-wifi ($WIFI_REF) e ne verifico lo SHA-256"
while IFS=: read -r path sum; do
    [ -n "$path" ] || continue
    curl -sSfL "$WIFI_RAW/$WIFI_REF/$path" -o "$WORK/$(basename "$path")" || die "Download di $path fallito."
    echo "$sum  $WORK/$(basename "$path")" | sha256sum -c --quiet - || die "SHA-256 di $path non corrisponde: mi fermo."
done <<< "$WIFI_FILES"
case "$f" in
    *.zst) zstd -dqc "$f" > "$WORK/brcmfmac43602-pcie.bin" ;;
    *.xz)  xz -dc "$f" > "$WORK/brcmfmac43602-pcie.bin" ;;
    *)     cp "$f" "$WORK/brcmfmac43602-pcie.bin" ;;
esac
# Lo script di setup controlla lo SHA-256 del firmware prima e dopo la patch.

if [ "$DRY_RUN" = 1 ]; then
    echo "[dry-run] installa in $SHARE e lancia: mbp143-wifi-setup install (Wi-Fi giù ~20 s)"
    echo "[dry-run] $NMCONF, $NMDISP"
    exit 0
fi

install -d "$SHARE"
install -m644 "$WORK"/{femPatch.txt,template.txt,sromTable.json,brcmfmac43602-pcie.bin} "$SHARE/"
install -m755 "$WORK/mbp143-wifi-setup" "$SETUP"

log "Configurazione NetworkManager (scansione senza MAC casuale, MAC stabile, preferenza 5 GHz)"
install_file 644 "$REPO_DIR/config/networkmanager/90-macbookpro14-3-wifi.conf" "$NMCONF"
install -Dm755 "$REPO_DIR/config/networkmanager/91-macbookpro14-3-wifi-prefer-5ghz" "$NMDISP"   # niente .bak: NM eseguirebbe anche la copia
nmcli general reload conf || true

log "Leggo la calibrazione del chip e scrivo NVRAM + firmware (il Wi-Fi cade per ~20 s)"
OUT="$(MBP143_WIFI_SHARE="$SHARE" python3 -I "$SETUP" install 2>&1)" || true
echo "$OUT"
if ! echo "$OUT" | grep -q 'wrote the board file and the firmware'; then
    die "Il setup non ha scritto NVRAM e firmware (vedi sopra). Nessun file installato in /usr/lib/firmware/updates."
fi

sleep 15
iw phy 2>/dev/null | grep -q 'Band 2' && ok "5 GHz disponibili." || warn "Band 2 (5 GHz) non ancora visibile: controlla con 'iw phy | grep Band'."
ok "Wi-Fi: NVRAM e firmware in /usr/lib/firmware/updates/brcm, valori del chip in /var/lib/mbp143-wifi."
