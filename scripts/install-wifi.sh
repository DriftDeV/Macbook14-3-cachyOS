#!/usr/bin/env bash
# Wi-Fi BCM43602 del MacBookPro14,3: 5 GHz, segnale pieno, canali a 80 MHz.
#
# Genera il file NVRAM dalla calibrazione di fabbrica del chip di questo Mac (SROM) e scrive
# il firmware di linux-firmware con la tabella front-end Apple (dnlbtz/mbp143-wifi, vedi
# config/sources.conf), più la configurazione di NetworkManager e/o iwd (Omarchy usa iwd senza NetworkManager).
# Il Wi-Fi cade per ~20 s.
#   sudo scripts/install-wifi.sh            installa
#   sudo scripts/install-wifi.sh --dry-run  mostra soltanto
#   sudo scripts/install-wifi.sh --undo     rimuove (torna a linux-firmware senza NVRAM)
#   sudo scripts/install-wifi.sh --files DIR  senza rete: i 4 file di mbp143-wifi già scaricati in DIR (per esempio
#                                           <chiavetta>/macbook14-3/wifi/mbp143-wifi, da omarchy/prepare-usb.sh)
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
IWDCONF=/etc/iwd/main.conf
IWD_MARK="# macbookpro14-3: brcmfmac perde le reti a 5 GHz se il MAC cambia durante la scansione (docs/wifi.md)"

uses_nm()  { command -v nmcli >/dev/null 2>&1; }
uses_iwd() { command -v iwctl >/dev/null 2>&1 || [ -x /usr/lib/iwd/iwd ]; }

# iwd non ha cartelle di drop-in: in /etc/iwd/main.conf metto (add) o tolgo (remove) solo la riga
# DisableMacAddressRandomization=true della sezione [Scan], preceduta da $IWD_MARK.
iwd_conf() {
    python3 -I - "$1" "$IWDCONF" "$IWD_MARK" <<'PY'
import os, sys
action, path, mark = sys.argv[1:4]
key = "DisableMacAddressRandomization"
was = "#macbookpro14-3-era: "          # prefisso della riga dell'utente messa da parte (ripristinata da remove)
created = mark + " [sezione aggiunta]"
lines = open(path).read().splitlines() if os.path.exists(path) else []
out, skip = [], 0
for l in lines:                       # stato pulito: via le nostre righe, rimesse quelle dell'utente
    if skip:
        skip -= 1
        continue
    s = l.strip()
    if s == mark:
        skip = 1                      # marcatore + nostra riga
        continue
    if s == created:
        skip = 2                      # marcatore + [Scan] + nostra riga
        if out and not out[-1].strip():
            out.pop()
        continue
    out.append(l[len(was):] if l.startswith(was) else l)
if action == "add":
    sec = None
    for i, l in enumerate(out):       # metti da parte altri valori della chiave in [Scan]
        s = l.strip()
        if s.startswith("["):
            sec = s
        elif sec == "[Scan]" and s.split("=")[0].strip() == key:
            out[i] = was + l
    names = [l.strip() for l in out]
    if "[Scan]" in names:
        j = names.index("[Scan]") + 1
        out[j:j] = [mark, key + "=true"]
    else:
        out += ([""] if out else []) + [created, "[Scan]", key + "=true"]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write("\n".join(out) + "\n")
elif any(l.strip() for l in out):
    open(path, "w").write("\n".join(out) + "\n")
elif os.path.exists(path):
    os.remove(path)                   # c'era solo quello che avevamo messo noi
PY
}

UNDO=0 FILES_DIR=""
while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=1 ;;
        --undo) UNDO=1 ;;
        --files) FILES_DIR="${2:-}"; shift; [ -d "$FILES_DIR" ] || die "--files: cartella $FILES_DIR non trovata" ;;
        *) die "Opzione sconosciuta: $1" ;;
    esac
    shift
done
need_root

if [ "$UNDO" = 1 ]; then
    if [ -f "$SETUP" ]; then run env MBP143_WIFI_SHARE="$SHARE" python3 -I "$SETUP" remove; fi
    run rm -rf "$SHARE"
    run rm -f "$NMCONF" "$NMDISP"
    if uses_nm; then run nmcli general reload conf || true; fi
    if [ -f "$IWDCONF" ] && grep -qF "$IWD_MARK" "$IWDCONF"; then
        if [ "$DRY_RUN" = 1 ]; then
            echo "[dry-run] tolgo da $IWDCONF la riga DisableMacAddressRandomization di questa repo"
        else
            iwd_conf remove
            systemctl try-restart iwd.service || true
        fi
    fi
    ok "Rimosso: il chip torna al firmware di linux-firmware senza file NVRAM (solo 2,4 GHz)."
    exit 0
fi

[ "$(cat /sys/class/dmi/id/product_name 2>/dev/null)" = MacBookPro14,3 ] || [ "${FORCE:-0}" = 1 ] \
    || die "Solo per MacBookPro14,3: template e tabella front-end sono di questa scheda."
grep -qx 0x43ba /sys/bus/pci/devices/*/device 2>/dev/null || die "Nessun BCM43602 (14e4:43ba) trovato."
# Omarchy (e altri) possono installare il driver proprietario "wl" (broadcom-wl), che toglie di mezzo brcmfmac:
# questo script lavora su brcmfmac, l'unico con cui il 5 GHz del BCM43602 è stato provato.
if lsmod 2>/dev/null | grep -qw '^wl' || pacman -Q broadcom-wl broadcom-wl-dkms >/dev/null 2>&1 \
        || grep -qsrw 'blacklist brcmfmac' /etc/modprobe.d /usr/lib/modprobe.d; then
    warn "Trovato il driver Broadcom proprietario (wl) o brcmfmac bloccato: questo passo usa brcmfmac."
    warn "Rimuovi broadcom-wl / il blacklist di brcmfmac e riavvia, poi rilancia: sudo ./install.sh --only wifi"
fi
for c in python3 zstd sha256sum modprobe; do
    command -v "$c" >/dev/null || die "$c non installato."
done
uses_nm || uses_iwd || warn "Né NetworkManager né iwd trovati: installo solo NVRAM e firmware."
for f in "$FW" "$FW.zst" "$FW.xz"; do [ -e "$f" ] && break; done
[ -e "$f" ] || die "Firmware $FW non trovato: installa linux-firmware-broadcom."

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
if [ -n "$FILES_DIR" ]; then log "File di mbp143-wifi da $FILES_DIR (verifico lo SHA-256)"
else
    command -v curl >/dev/null || die "curl non installato."
    log "Scarico i file di mbp143-wifi ($WIFI_REF) e ne verifico lo SHA-256"
fi
while IFS=: read -r path sum; do
    [ -n "$path" ] || continue
    if [ -n "$FILES_DIR" ]; then
        cp "$FILES_DIR/$(basename "$path")" "$WORK/" || die "$(basename "$path") non trovato in $FILES_DIR."
    else
        curl -sSfL "$WIFI_RAW/$WIFI_REF/$path" -o "$WORK/$(basename "$path")" || die "Download di $path fallito."
    fi
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
    if uses_nm; then echo "[dry-run] NetworkManager: $NMCONF, $NMDISP"; fi
    if uses_iwd; then echo "[dry-run] iwd: [Scan] DisableMacAddressRandomization=true in $IWDCONF, riavvio di iwd"; fi
    exit 0
fi

install -d "$SHARE"
install -m644 "$WORK"/{femPatch.txt,template.txt,sromTable.json,brcmfmac43602-pcie.bin} "$SHARE/"
install -m755 "$WORK/mbp143-wifi-setup" "$SETUP"

if uses_nm; then
    log "Configurazione NetworkManager (scansione senza MAC casuale, MAC stabile, preferenza 5 GHz)"
    install_file 644 "$REPO_DIR/config/networkmanager/90-macbookpro14-3-wifi.conf" "$NMCONF"
    install -Dm755 "$REPO_DIR/config/networkmanager/91-macbookpro14-3-wifi-prefer-5ghz" "$NMDISP"   # niente .bak: NM eseguirebbe anche la copia
    nmcli general reload conf || true
fi
if uses_iwd; then
    log "Configurazione iwd (scansione senza MAC casuale) in $IWDCONF"
    if [ -f "$IWDCONF" ] && [ ! -e "$IWDCONF.bak" ]; then cp -a "$IWDCONF" "$IWDCONF.bak"; fi
    iwd_conf add
    systemctl try-restart iwd.service || true
fi

log "Leggo la calibrazione del chip e scrivo NVRAM + firmware (il Wi-Fi cade per ~20 s)"
OUT="$(MBP143_WIFI_SHARE="$SHARE" python3 -I "$SETUP" install 2>&1)" || true
echo "$OUT"
if ! echo "$OUT" | grep -q 'wrote the board file and the firmware'; then
    die "Il setup non ha scritto NVRAM e firmware (vedi sopra). Nessun file installato in /usr/lib/firmware/updates."
fi

sleep 15
if iw phy 2>/dev/null | grep -q 'Band 2'; then
    ok "5 GHz disponibili."
else
    warn "Band 2 (5 GHz) non ancora visibile: controlla con 'iw phy | grep Band'."
fi
ok "Wi-Fi: NVRAM e firmware in /usr/lib/firmware/updates/brcm, valori del chip in /var/lib/mbp143-wifi."
