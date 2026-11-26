#!/bin/bash
# Chiavetta USB per installare Omarchy sul MacBookPro14,3, preparata da macOS o da Linux.
#
# Perché una chiavetta: l'installatore di Omarchy esclude il disco da cui è partita la live, quindi una live messa
# sul disco interno (come cachyos/macos/prepare.sh fa per CachyOS) non trova il disco su cui installare [F, 26/11/2026].
#
# Cosa mette sulla chiavetta (FAT32, etichetta OMARCHY):
#   - la ISO di Omarchy estratta, con l'avvio che cerca la chiavetta per etichetta (archisolabel=OMARCHY), così la live
#     resta modificabile (una ISO scritta con dd sarebbe in sola lettura);
#   - macbook14-3/efi-backup: copia della partizione EFI di Apple (EFI/APPLE = firmware del chip T1: Touch Bar, Touch ID,
#     webcam, sensore di luce; EFI/OC se c'è) con SHA256SUMS e ripristina.sh. L'installatore di Omarchy cancella TUTTO
#     il disco, partizione EFI di Apple compresa: senza questa copia il T1 resta senza firmware;
#   - macbook14-3/wifi-live.sh + macbook14-3/wifi: Wi-Fi del BCM43602 nella live (senza file NVRAM il chip va male o
#     non va). Preparata su Linux su questo stesso Mac, con il Wi-Fi già sistemato (scripts/install-wifi.sh), copia
#     NVRAM e firmware pronti; altrimenti li genera nella live dal chip con mbp143-wifi (serve python3 nella live [NV]).
#     Con --embed-wifi (solo Linux) li mette direttamente dentro la live: niente comando da lanciare;
#   - Macbook14-3-cachyOS.tar.gz: questa repo, per il post-installazione anche senza rete.
#
# Uso (da root: sudo su macOS e su Linux, run0 su Omarchy):
#   omarchy/prepare-usb.sh --iso omarchy-X.Y.Z-x86.iso --device /dev/sdX            piano, non cambia niente
#   omarchy/prepare-usb.sh --iso ... --device /dev/sdX --execute                    esegue (chiede conferma scritta)
#   Opzioni: --sha256 HASH (verifica la ISO), --embed-wifi (solo Linux, vedi sopra), --no-efi-backup (sconsigliato)
#   macOS: --device diskN (vedi "diskutil list external"); Linux: --device /dev/sdX (vedi "lsblk -o NAME,TRAN,SIZE,MODEL")
#
# Compatibile con bash 3.2 (quella di macOS). La ISO non viene scaricata da qui: prendila dal sito di Omarchy.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
LABEL=OMARCHY
ISO="" SHA="" DEV="" EXECUTE=0 EMBED_WIFI=0 EFI_BACKUP=1
OS="$(uname -s)"
FAT_MAX=4294967295

log()  { printf '\033[1;34m[*]\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m[ok]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }
usage() { sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'; }

while [ $# -gt 0 ]; do
    case "$1" in
        --iso) ISO="${2:-}"; shift ;;
        --sha256) SHA="${2:-}"; shift ;;
        --device) DEV="${2:-}"; shift ;;
        --execute) EXECUTE=1 ;;
        --embed-wifi) EMBED_WIFI=1 ;;
        --no-efi-backup) EFI_BACKUP=0 ;;
        -h|--help) usage; exit 0 ;;
        *) usage; die "Opzione sconosciuta: $1" ;;
    esac
    shift
done

sha256_of() { if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }
# SHA256SUMS di una cartella (stesso formato su macOS e Linux: "hash  ./percorso").
sums_of() {
    ( cd "$1" && find . -type f ! -name SHA256SUMS | LC_ALL=C sort | while IFS= read -r f; do
        printf '%s  %s\n' "$(sha256_of "$f")" "$f"; done )
}
# sed -i portabile (BSD e GNU).
sed_i() { local expr="$1"; shift; local f; for f in "$@"; do sed -e "$expr" "$f" > "$f.tmp" && mv "$f.tmp" "$f"; done; }

# ------------------------------------------------------------------ controlli
case "$OS" in Darwin|Linux) ;; *) die "Sistema non supportato: $OS (serve macOS o Linux)." ;; esac
[ -n "$ISO" ] && [ -f "$ISO" ] || { usage; die "Indica la ISO di Omarchy con --iso (scaricala dal sito di Omarchy)."; }
[ -n "$DEV" ] || { usage; die "Indica la chiavetta con --device."; }
command -v bsdtar >/dev/null || command -v tar >/dev/null || die "Serve bsdtar (Linux: pacman -S libarchive)."
TAR=bsdtar; command -v bsdtar >/dev/null || TAR=tar   # su macOS tar è bsdtar
[ "$OS" = Darwin ] || command -v bsdtar >/dev/null || die "Serve bsdtar per leggere la ISO (pacman -S libarchive)."
if [ "$EMBED_WIFI" = 1 ]; then
    [ "$OS" = Linux ] || die "--embed-wifi funziona solo da Linux (squashfs con permessi e nomi Linux)."
    command -v unsquashfs >/dev/null && command -v mksquashfs >/dev/null || die "--embed-wifi: serve squashfs-tools."
fi

# Chiavetta: deve essere un disco esterno/rimovibile, mai il disco interno.
if [ "$OS" = Darwin ]; then
    DEV="${DEV#/dev/}"
    case "$DEV" in disk[0-9]|disk[0-9][0-9]) ;; *) die "--device vuole un disco intero, per esempio disk4." ;; esac
    INFO="$(diskutil info "$DEV" 2>/dev/null)" || die "$DEV non trovato (diskutil list external)."
    echo "$INFO" | grep -Eq 'Device Location: +External|Removable Media: +(Removable|Yes)' \
        || die "$DEV non risulta esterno o rimovibile: mi fermo (non tocco dischi interni)."
    SIZE_DESC="$(echo "$INFO" | awk -F: '/Disk Size/{print $2; exit}' | sed 's/^ *//')"
    MODEL="$(echo "$INFO" | awk -F: '/Media Name/{print $2; exit}' | sed 's/^ *//')"
else
    [ -b "$DEV" ] || die "$DEV non è un disco (lsblk -o NAME,TRAN,SIZE,MODEL)."
    [ "$(lsblk -dno TYPE "$DEV")" = disk ] || die "--device vuole un disco intero (/dev/sdX), non una partizione."
    TRAN="$(lsblk -dno TRAN "$DEV" | tr -d ' ')"; RM="$(lsblk -dno RM "$DEV" | tr -d ' ')"
    [ "$TRAN" = usb ] || [ "$RM" = 1 ] || die "$DEV non è USB né rimovibile ($TRAN): mi fermo (non tocco dischi interni)."
    if lsblk -nro MOUNTPOINTS "$DEV" 2>/dev/null | grep -Eqx '/|/boot|/home|\[SWAP\]'; then
        die "$DEV contiene il sistema in uso: mi fermo."
    fi
    SIZE_DESC="$(lsblk -dno SIZE "$DEV" | tr -d ' ')"; MODEL="$(lsblk -dno MODEL "$DEV" | sed 's/ *$//')"
fi

# La ISO: checksum e file più grande (FAT32 non regge file da 4 GiB in su).
if [ -n "$SHA" ]; then
    log "Verifico lo SHA-256 della ISO"
    [ "$(sha256_of "$ISO")" = "$(echo "$SHA" | tr 'A-F' 'a-f')" ] || die "SHA-256 della ISO diverso da quello atteso."
    ok "SHA-256 corretto."
else
    warn "Nessun --sha256: la ISO non viene verificata (il valore è sul sito di Omarchy)."
fi
BIGGEST="$($TAR -tvf "$ISO" | awk '{ if ($5+0 > m) m = $5+0 } END { printf "%d", m }')"
[ "$BIGGEST" -le "$FAT_MAX" ] || die "La ISO contiene un file da $BIGGEST byte: non entra in FAT32."
ISO_BYTES="$(wc -c < "$ISO" | tr -d ' ')"

# Wi-Fi: NVRAM e firmware pronti solo se siamo su Linux su un 14,3 con il Wi-Fi già sistemato.
PREBUILT=""
if [ "$OS" = Linux ] && [ "$(cat /sys/class/dmi/id/product_name 2>/dev/null)" = MacBookPro14,3 ]; then
    for f in /usr/lib/firmware/updates/brcm/brcmfmac43602-pcie.*MacBookPro14,3.txt; do
        [ -f "$f" ] && [ -f /usr/lib/firmware/updates/brcm/brcmfmac43602-pcie.bin ] && PREBUILT=/usr/lib/firmware/updates/brcm
    done
fi
[ "$EMBED_WIFI" = 0 ] || [ -n "$PREBUILT" ] \
    || die "--embed-wifi: servono NVRAM e firmware già generati su questo Mac (sudo scripts/install-wifi.sh)."

cat <<EOF

Piano ($OS):
  ISO:        $ISO ($ISO_BYTES byte, file più grande $BIGGEST byte)
  Chiavetta:  $DEV  $MODEL  $SIZE_DESC   -> CANCELLATA, FAT32 "$LABEL"
  Avvio:      archisosearchuuid=... -> archisolabel=$LABEL (grub, syslinux, systemd-boot)
  EFI Apple:  $( [ "$EFI_BACKUP" = 1 ] && echo "copia di EFI/APPLE (+ EFI/OC) in macbook14-3/efi-backup, con SHA256SUMS e ripristina.sh" || echo "NESSUNA copia (--no-efi-backup)")
  Wi-Fi live: $( if [ -n "$PREBUILT" ]; then echo "NVRAM + firmware di questo Mac"; else echo "generati nella live dal chip (mbp143-wifi, serve python3 nella live [NV])"; fi )$( [ "$EMBED_WIFI" = 1 ] && echo ", dentro airootfs.sfs (nessun comando nella live)" )
  Repo:       Macbook14-3-cachyOS.tar.gz
EOF
if [ "$EXECUTE" = 0 ]; then
    echo; log "Prova: niente è stato cambiato. Aggiungi --execute per preparare la chiavetta."
    exit 0
fi
[ "$(id -u)" = 0 ] || die "Serve root: sudo (su Omarchy: run0) $0 ..."
printf '\nTutto quello che c'"'"'è su %s (%s %s) verrà cancellato. Scrivi CANCELLA per continuare: ' "$DEV" "$MODEL" "$SIZE_DESC"
read -r answer
[ "$answer" = CANCELLA ] || die "Annullato."

# ------------------------------------------------------------------ formattazione
MNT=""
cleanup() {
    if [ -n "$MNT" ] && [ "$OS" = Linux ] && mountpoint -q "$MNT" 2>/dev/null; then umount "$MNT" || true; rmdir "$MNT" || true; fi
}
trap cleanup EXIT
if [ "$OS" = Darwin ]; then
    log "Formatto $DEV (GPT, FAT32 $LABEL)"
    diskutil unmountDisk "$DEV" >/dev/null 2>&1 || true
    diskutil eraseDisk FAT32 "$LABEL" GPT "$DEV"
    MNT="/Volumes/$LABEL"
    [ -d "$MNT" ] || die "Volume $MNT non montato dopo la formattazione."
else
    log "Formatto $DEV (GPT, una partizione EFI FAT32 $LABEL)"
    for p in $(lsblk -nro PATH "$DEV" | tail -n +2); do umount "$p" 2>/dev/null || true; done
    wipefs -a "$DEV" >/dev/null
    printf 'label: gpt\n,,U\n' | sfdisk --quiet "$DEV"
    partprobe "$DEV" 2>/dev/null || true; udevadm settle 2>/dev/null || sleep 2
    PART="$(lsblk -nro PATH "$DEV" | sed -n 2p)"
    [ -b "$PART" ] || die "Partizione nuova non trovata su $DEV."
    mkfs.fat -F 32 -n "$LABEL" "$PART" >/dev/null
    MNT="$(mktemp -d)"
    mount "$PART" "$MNT"
fi

# ------------------------------------------------------------------ ISO
log "Copio la ISO sulla chiavetta (qualche minuto)"
$TAR -xf "$ISO" -C "$MNT" --no-same-owner --no-same-permissions 2>/dev/null || $TAR -xf "$ISO" -C "$MNT"
chmod -R u+w "$MNT" 2>/dev/null || true
CFGS=""
for f in "$MNT"/boot/grub/*.cfg "$MNT"/boot/syslinux/*.cfg "$MNT"/loader/entries/*.conf; do
    [ -f "$f" ] && grep -q 'archisosearchuuid=' "$f" && CFGS="$CFGS $f"
done
if [ -n "$CFGS" ]; then
    # shellcheck disable=SC2086
    sed_i "s/archisosearchuuid=[^ ]*/archisolabel=$LABEL/g" $CFGS
    ok "Avvio per etichetta in:$(echo "$CFGS" | sed "s#$MNT/##g")"
elif grep -rqs "archisolabel=" "$MNT/boot" "$MNT/loader" 2>/dev/null; then
    warn "La ISO usa archisolabel: controlla che l'etichetta sia $LABEL (altrimenti la live non trova i suoi file)."
else
    warn "Nessun archisosearchuuid/archisolabel trovato nei file di avvio: la live potrebbe non trovare i suoi file."
fi

# ------------------------------------------------------------------ copia della EFI di Apple
D="$MNT/macbook14-3"
mkdir -p "$D"
if [ "$EFI_BACKUP" = 1 ]; then
    log "Copia della partizione EFI di Apple (firmware del T1)"
    ESP_DIR="" ESP_TMP=""
    if [ "$OS" = Darwin ]; then
        diskutil mount disk0s1 >/dev/null 2>&1 || true
        ESP_DIR="$(diskutil info disk0s1 | awk -F: '/Mount Point/{print $2; exit}' | sed 's/^ *//')"
    else
        # Prima le partizioni vfat già montate (su Omarchy/CachyOS è /boot), poi le EFI non montate, in sola lettura.
        for t in $(findmnt -rn -t vfat -o TARGET); do [ -d "$t/EFI/APPLE" ] && { ESP_DIR="$t"; break; }; done
        if [ -z "$ESP_DIR" ]; then
            for p in $(lsblk -rno PATH,PARTTYPE | awk 'tolower($2)=="c12a7328-f81f-11d2-ba4b-00a0c93ec93b"{print $1}'); do
                ESP_TMP="$(mktemp -d)"
                if mount -o ro "$p" "$ESP_TMP" 2>/dev/null; then
                    [ -d "$ESP_TMP/EFI/APPLE" ] && { ESP_DIR="$ESP_TMP"; break; }
                    umount "$ESP_TMP"
                fi
                rmdir "$ESP_TMP"; ESP_TMP=""
            done
        fi
    fi
    [ -n "$ESP_DIR" ] && [ -d "$ESP_DIR/EFI/APPLE" ] || die "Partizione EFI con EFI/APPLE non trovata: senza questa copia NON installare Omarchy."
    [ -f "$ESP_DIR/EFI/APPLE/EMBEDDEDOS/combined.memboot" ] || warn "Manca EFI/APPLE/EMBEDDEDOS/combined.memboot (firmware del T1)."
    [ -f "$ESP_DIR/EFI/APPLE/EMBEDDEDOS/FDRData" ] || warn "Manca EFI/APPLE/EMBEDDEDOS/FDRData (calibrazione di Touch ID, docs/touchid-t1.md)."
    B="$D/efi-backup"
    mkdir -p "$B/EFI"
    cp -R "$ESP_DIR/EFI/APPLE" "$B/EFI/"
    [ -d "$ESP_DIR/EFI/OC" ] && cp -R "$ESP_DIR/EFI/OC" "$B/EFI/"
    [ -n "$ESP_TMP" ] && { umount "$ESP_TMP"; rmdir "$ESP_TMP"; }
    sums_of "$B" > "$B/SHA256SUMS"
    ( cd "$B" && while IFS= read -r line; do
        h="${line%%  *}"; f="${line#*  }"
        [ "$(sha256_of "$f")" = "$h" ] || die "Copia di $f diversa dall'originale."
      done < SHA256SUMS )
    ok "EFI/APPLE$( [ -d "$B/EFI/OC" ] && echo ' + EFI/OC') copiati e verificati ($(wc -l < "$B/SHA256SUMS" | tr -d ' ') file)."
    cat > "$B/ripristina.sh" <<'EOF'
#!/bin/bash
# Rimette EFI/APPLE (firmware del T1) e, se c'era, EFI/OC nella partizione EFI indicata, dopo l'installazione di Omarchy.
#   sudo bash ripristina.sh /boot          dal sistema installato (Omarchy monta la partizione EFI su /boot)
# Copia solo i file mancanti; quelli presenti ma diversi li segnala senza toccarli. Poi: spegnimento completo, ~30 s,
# riaccensione (il Mac carica il firmware nel T1 solo all'accensione).
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
ESP="${1:?Uso: ripristina.sh <partizione EFI montata, per esempio /boot>}"
[ -d "$ESP/EFI" ] || { echo "$ESP non sembra una partizione EFI (manca EFI/)." >&2; exit 1; }
cd "$HERE"
sha256sum -c --quiet SHA256SUMS || { echo "La copia sulla chiavetta è rovinata: mi fermo." >&2; exit 1; }
added=0 differ=0
while IFS= read -r line; do
    h="${line%%  *}"; f="${line#*  ./}"
    if [ ! -e "$ESP/$f" ]; then
        install -D -m644 "$f" "$ESP/$f"; added=$((added + 1))
    elif [ "$(sha256sum "$ESP/$f" | cut -d' ' -f1)" != "$h" ]; then
        echo "diverso (non toccato): $ESP/$f" >&2; differ=$((differ + 1))
    fi
done < SHA256SUMS
sync
echo "Aggiunti $added file, $differ diversi. Ora spegni completamente il Mac, aspetta ~30 s e riaccendi."
EOF
    chmod +x "$B/ripristina.sh" 2>/dev/null || true
fi

# ------------------------------------------------------------------ Wi-Fi della live
log "Wi-Fi per la live"
W="$D/wifi"
mkdir -p "$W/mbp143-wifi"
# shellcheck source=config/sources.conf
. "$REPO_DIR/config/sources.conf"
echo "$WIFI_FILES" | while IFS=: read -r path sum; do
    [ -n "$path" ] || continue
    out="$W/mbp143-wifi/$(basename "$path")"
    curl -sSfL "$WIFI_RAW/$WIFI_REF/$path" -o "$out" || die "Download di $path fallito (serve la rete)."
    [ "$(sha256_of "$out")" = "$sum" ] || die "SHA-256 di $path diverso: mi fermo."
done
if [ -n "$PREBUILT" ]; then
    mkdir -p "$W/prebuilt"
    cp "$PREBUILT"/brcmfmac43602-pcie.*MacBookPro14,3.txt "$PREBUILT/brcmfmac43602-pcie.bin" "$W/prebuilt/"
    [ -f /usr/share/macbookpro14-3/wifi/brcmfmac43602-pcie.bin ] \
        && cp /usr/share/macbookpro14-3/wifi/brcmfmac43602-pcie.bin "$W/mbp143-wifi/"   # firmware originale, per rigenerare
    ok "NVRAM e firmware di questo Mac copiati (file personali del chip: non ridistribuirli)."
fi
cp "$SCRIPT_DIR/wifi-live.sh" "$D/wifi-live.sh"

if [ "$EMBED_WIFI" = 1 ]; then
    SFS="$MNT/arch/x86_64/airootfs.sfs"
    [ -f "$SFS" ] || die "--embed-wifi: $SFS non trovato."
    WORK="$(mktemp -d /var/tmp/omarchy-sfs.XXXXXX)"
    log "Ricostruisco airootfs.sfs con NVRAM e firmware (in $WORK, diversi GB e qualche minuto)"
    COMP="$(unsquashfs -s "$SFS" | awk '/^Compression/{print $2}')"; COMP="${COMP:-zstd}"
    BLOCK="$(unsquashfs -s "$SFS" | awk '/^Block size/{print $3}')"; BLOCK="${BLOCK:-1048576}"
    unsquashfs -q -d "$WORK/root" "$SFS"
    install -d "$WORK/root/usr/lib/firmware/updates/brcm"
    cp "$W"/prebuilt/* "$WORK/root/usr/lib/firmware/updates/brcm/"
    # iwd: niente MAC casuale durante la scansione (brcmfmac perde le reti a 5 GHz, docs/wifi.md).
    install -d "$WORK/root/etc/iwd"
    if ! grep -qs DisableMacAddressRandomization "$WORK/root/etc/iwd/main.conf"; then
        printf '\n[Scan]\nDisableMacAddressRandomization=true\n' >> "$WORK/root/etc/iwd/main.conf"
    fi
    extra=""; [ "$COMP" = zstd ] && extra="-Xcompression-level 19"
    # shellcheck disable=SC2086
    mksquashfs "$WORK/root" "$WORK/airootfs.sfs" -comp "$COMP" $extra -b "$BLOCK" -noappend -quiet
    [ "$(wc -c < "$WORK/airootfs.sfs")" -le "$FAT_MAX" ] || die "airootfs.sfs ricostruito supera i 4 GiB."
    mv "$WORK/airootfs.sfs" "$SFS"
    if [ -f "$MNT/arch/x86_64/airootfs.sha512" ]; then
        ( cd "$MNT/arch/x86_64" && sha512sum airootfs.sfs > airootfs.sha512 )
    fi
    [ -f "$SFS.sig" ] && { rm -f "$SFS.sig"; warn "Firma airootfs.sfs.sig tolta (non vale più per l'immagine modificata)."; }
    rm -rf "$WORK"
    ok "Wi-Fi già dentro la live."
fi

# ------------------------------------------------------------------ repo
log "Copio questa repo (Macbook14-3-cachyOS.tar.gz)"
( cd "$(dirname "$REPO_DIR")" && tar -czf "$MNT/Macbook14-3-cachyOS.tar.gz" \
    --exclude='*/target' --exclude='*.iso' "$(basename "$REPO_DIR")" )

sync
if [ "$OS" = Darwin ]; then diskutil eject "$DEV" >/dev/null && ok "Chiavetta espulsa."
else umount "$MNT" && rmdir "$MNT" && MNT="" && ok "Chiavetta smontata."; fi

cat <<EOF

Pronta. Sul MacBook (alimentatore collegato, tastiera USB-C a portata di mano se puoi):
  1. Accendi tenendo premuto Option (⌥) e scegli "EFI Boot".
  2. Wi-Fi nella live$( [ "$EMBED_WIFI" = 1 ] && echo ' (già sistemato: salta)'):  bash /run/archiso/bootmnt/macbook14-3/wifi-live.sh
  3. Installa Omarchy (prende tutto il disco interno).
  4. Nel sistema installato: rimetti il firmware del T1 (la chiavetta si monta da sola o con il file manager)
       sudo bash <chiavetta>/macbook14-3/efi-backup/ripristina.sh /boot
     poi spegnimento completo, ~30 s, riaccensione.
  5. Post-installazione: tar -xzf <chiavetta>/Macbook14-3-cachyOS.tar.gz -C ~ && cd ~/Macbook14-3-cachyOS
       sudo ./install.sh --wifi-files <chiavetta>/macbook14-3/wifi/mbp143-wifi
EOF
