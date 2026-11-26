#!/bin/bash
# Wi-Fi del BCM43602 nella live di Omarchy sul MacBookPro14,3 (copiato sulla chiavetta da omarchy/prepare-usb.sh):
#   bash /run/archiso/bootmnt/macbook14-3/wifi-live.sh
# Senza il file NVRAM della scheda il chip parte con valori generici (niente 5 GHz, segnale debole: docs/wifi.md).
# Vale solo per la live (sparisce al riavvio); nel sistema installato ci pensa install.sh (passo wifi).
#   - con macbook14-3/wifi/prebuilt (chiavetta preparata da Linux su questo Mac): copia NVRAM e firmware;
#   - altrimenti li genera dal chip con mbp143-wifi (python3 nella live [NV]; il firmware di linux-firmware della
#     live deve essere quello atteso da mbp143-wifi, che lo controlla con SHA-256).
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
W="$HERE/wifi"
U=/usr/lib/firmware/updates/brcm
[ "$(id -u)" = 0 ] || exec sudo bash "$0" "$@"

reload() {
    for m in brcmfmac_wcc brcmfmac; do modprobe -r "$m" 2>/dev/null || true; done
    modprobe brcmfmac
}

if ls "$W"/prebuilt/brcmfmac43602-pcie.*.txt >/dev/null 2>&1; then
    mkdir -p "$U"
    cp "$W"/prebuilt/* "$U/"
    echo "NVRAM e firmware di questo Mac copiati in $U."
    NEED_RELOAD=1
elif command -v python3 >/dev/null; then
    T="$(mktemp -d)"
    cp "$W"/mbp143-wifi/* "$T/"
    if [ ! -f "$T/brcmfmac43602-pcie.bin" ]; then
        f=/usr/lib/firmware/brcm/brcmfmac43602-pcie.bin
        if [ -f "$f" ]; then cp "$f" "$T/"
        elif [ -f "$f.zst" ]; then zstd -dqc "$f.zst" > "$T/brcmfmac43602-pcie.bin"
        elif [ -f "$f.xz" ]; then xz -dc "$f.xz" > "$T/brcmfmac43602-pcie.bin"
        else echo "Firmware $f non trovato nella live." >&2; exit 1; fi
    fi
    echo "Genero NVRAM e firmware dalla calibrazione del chip (il Wi-Fi cade per ~20 s)..."
    MBP143_WIFI_SHARE="$T" python3 -I "$T/mbp143-wifi-setup" install   # ricarica brcmfmac da solo
    NEED_RELOAD=0
else
    echo "Né file pronti né python3: nella live il Wi-Fi resta con i valori generici." >&2
    echo "Prepara la chiavetta da Linux su questo Mac (omarchy/prepare-usb.sh), oppure usa una rete via USB." >&2
    exit 1
fi

# iwd: niente MAC casuale durante la scansione (con brcmfmac le reti a 5 GHz sparirebbero).
mkdir -p /etc/iwd
if ! grep -qs DisableMacAddressRandomization /etc/iwd/main.conf; then
    if grep -qs '^\[Scan\]' /etc/iwd/main.conf; then
        sed -i '/^\[Scan\]/a DisableMacAddressRandomization=true' /etc/iwd/main.conf
    else
        printf '\n[Scan]\nDisableMacAddressRandomization=true\n' >> /etc/iwd/main.conf
    fi
fi
[ "$NEED_RELOAD" = 1 ] && reload
systemctl try-restart iwd.service 2>/dev/null || true
sleep 8
if iw phy 2>/dev/null | grep -q 'Band 2'; then echo "5 GHz disponibili."
else echo "5 GHz non ancora visibili: riprova tra qualche secondo con 'iw phy | grep Band'."; fi
