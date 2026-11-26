#!/usr/bin/env bash
# OpenCore sul MacBookPro14,3 per avviare Linux (CachyOS, Omarchy) "come se fosse macOS" e scegliere la GPU dello schermo.
#
# Perché: senza macOS il firmware Apple collega il pannello alla Radeon e lascia la Intel senza schermo. Con OpenCore,
# Booter > Quirks > SignalAppleOS fa credere al firmware di avviare macOS; con in più la variabile EFI gpu-power-prefs
# = 01 il chip gmux collega il pannello alla Intel (provato il 25/11/2026, docs/gpu.md). Qui la variabile la scrive
# OpenCore a ogni avvio (NVRAM > Add/Delete), quindi cambiarla vuol dire cambiare una riga di config.plist.
# Vale dal riavvio successivo (il firmware legge la variabile prima di OpenCore: può servirne un secondo).
#
# Niente seriali: su un Mac vero OpenCore lascia al firmware i suoi dati (PlatformInfo con Automatic/UpdateSMBIOS/
# UpdateDataHub/UpdateNVRAM = false), come la EFI di OCLP di questo Mac. Nessuna kext: servono solo a macOS.
#
#   sudo scripts/opencore.sh status                    cosa c'è: OpenCore, SignalAppleOS, gpu-power-prefs, GPU dello schermo
#   sudo scripts/opencore.sh install [--from DIR]      mette OpenCore nella partizione EFI se manca (da DIR = una cartella
#                                                      EFI/OC salvata, per esempio dalla chiavetta di omarchy/prepare-usb.sh;
#                                                      altrimenti OpenCorePkg fissato in config/sources.conf con una
#                                                      configurazione generata) e la voce di avvio "OpenCore"
#   sudo scripts/opencore.sh install --rebuild         rigenera EFI/OC (il vecchio resta in EFI/OC.bak-<data>)
#   sudo scripts/opencore.sh gpu intel|radeon          GPU dello schermo dal prossimo avvio (con SignalAppleOS)
#   scripts/opencore.sh config --pkg DIR --out FILE [--gpu intel|radeon]   solo genera config.plist (usato dalla CI)
#   --dry-run mostra senza cambiare. Ogni config.plist toccato viene prima copiato in config.plist.bak-<data>.
#
# Se qualcosa va storto all'avvio: tieni premuto Option (⌥) e scegli "EFI Boot" (Limine/GRUB senza OpenCore, schermo
# sulla Radeon); dal menu di OpenCore c'è anche "Reset NVRAM". Stato: generazione [F] in CI con ocvalidate; avvio con la
# configurazione generata [NV] (quella di OCLP è provata).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=scripts/lib.sh
source "$SCRIPT_DIR/lib.sh"
# shellcheck source=config/sources.conf
source "$REPO_DIR/config/sources.conf"

GMUX_GUID=FA4CE28D-B62F-4C99-9CC3-6815686E30F9
EFIVAR="/sys/firmware/efi/efivars/gpu-power-prefs-${GMUX_GUID,,}"
STAMP="$(date +%Y%m%d-%H%M%S)"

CMD="${1:-status}"; shift || true
FROM="" REBUILD=0 PKG="" OUT="" GPU=""
while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=1 ;;
        --from) FROM="${2:-}"; shift ;;
        --rebuild) REBUILD=1 ;;
        --pkg) PKG="${2:-}"; shift ;;
        --out) OUT="${2:-}"; shift ;;
        --gpu) GPU="${2:-}"; shift ;;
        intel|radeon) GPU="$1" ;;
        *) die "Opzione sconosciuta: $1" ;;
    esac
    shift
done

# Partizione EFI montata: quella con EFI/OC o EFI/APPLE tra le vfat montate (Omarchy: /boot; CachyOS: /boot/efi).
find_esp() {
    local t
    for t in $(findmnt -rn -t vfat -o TARGET); do
        [ -d "$t/EFI/OC" ] && { echo "$t"; return; }
    done
    for t in $(findmnt -rn -t vfat -o TARGET); do
        [ -d "$t/EFI/APPLE" ] && { echo "$t"; return; }
    done
}

# Modifica (o genera) config.plist con plistlib. $1 = azione: generate SAMPLE OUT GPU | gpu FILE GPU | show FILE
plist() {
    python3 -I - "$@" <<'PY'
import plistlib, sys
GMUX = "FA4CE28D-B62F-4C99-9CC3-6815686E30F9"
action = sys.argv[1]

def set_gpu(p, gpu):
    p["Booter"]["Quirks"]["SignalAppleOS"] = True
    nv = p.setdefault("NVRAM", {})
    add, delete = nv.setdefault("Add", {}), nv.setdefault("Delete", {})
    if gpu == "intel":
        add.setdefault(GMUX, {})["gpu-power-prefs"] = b"\x01\x00\x00\x00"
    elif gpu == "radeon":
        add.setdefault(GMUX, {})["gpu-power-prefs"] = b"\x00\x00\x00\x00"
    # In Delete: OpenCore riscrive la variabile a ogni avvio (Add non sovrascrive una variabile già presente).
    dl = delete.setdefault(GMUX, [])
    if "gpu-power-prefs" not in dl:
        dl.append("gpu-power-prefs")
    nv["WriteFlash"] = True

if action == "generate":
    sample, out, gpu = sys.argv[2], sys.argv[3], sys.argv[4]
    p = plistlib.load(open(sample, "rb"))
    # Niente per macOS: ACPI, proprietà dei dispositivi, kext e patch del kernel.
    for a in p["ACPI"]["Add"]: a["Enabled"] = False
    for a in p["ACPI"].get("Patch", []): a["Enabled"] = False
    p["DeviceProperties"]["Add"] = {}
    p["Kernel"]["Add"] = []
    for k in ("Block", "Force", "Patch"):
        for e in p["Kernel"].get(k, []): e["Enabled"] = False
    # Booter come la EFI di OCLP di questo Mac: solo SignalAppleOS e ProtectSecureBoot.
    for k, v in list(p["Booter"]["Quirks"].items()):
        if isinstance(v, bool): p["Booter"]["Quirks"][k] = False
    p["Booter"]["Quirks"]["ProtectSecureBoot"] = True
    for e in p["Booter"].get("Patch", []): e["Enabled"] = False
    for e in p["Booter"].get("MmioWhitelist", []): e["Enabled"] = False
    # Driver: runtime, Linux, voce "Reset NVRAM" nel menu (via d'uscita).
    want = {"OpenRuntime.efi", "OpenLinuxBoot.efi", "ResetNvramEntry.efi"}
    for d in p["UEFI"]["Drivers"]: d["Enabled"] = d["Path"] in want
    p["UEFI"]["Quirks"].update({"RequestBootVarRouting": True, "EnableVectorAcceleration": True})
    p["UEFI"]["Output"].update({"ProvideConsoleGop": True, "Resolution": "Max"})
    p["UEFI"]["APFS"]["EnableJumpstart"] = False
    b = p["Misc"]["Boot"]
    b.update({"PickerMode": "Builtin", "ShowPicker": True, "Timeout": 5, "HideAuxiliary": True,
              "PollAppleHotKeys": True, "LauncherOption": "Full", "LauncherPath": "Default"})
    s = p["Misc"]["Security"]
    s.update({"ScanPolicy": 0, "SecureBootModel": "Disabled", "Vault": "Optional", "AllowSetDefault": True,
              "DmgLoading": "Signed", "ExposeSensitiveData": 6})
    p["Misc"]["Entries"] = []
    for t in p["Misc"]["Tools"]: t["Enabled"] = t["Path"] == "OpenShell.efi"
    # Dati del Mac vero: OpenCore non tocca SMBIOS/DataHub/NVRAM della piattaforma (nessun seriale serve).
    pi = p["PlatformInfo"]
    pi.update({"Automatic": False, "UpdateSMBIOS": False, "UpdateDataHub": False, "UpdateNVRAM": False,
               "CustomMemory": False})
    # NVRAM: solo la variabile del gmux (niente boot-args/csr di macOS).
    p["NVRAM"]["Add"] = {}
    p["NVRAM"]["Delete"] = {}
    set_gpu(p, gpu or "radeon")
    plistlib.dump(p, open(out, "wb"))
elif action == "gpu":
    f, gpu = sys.argv[2], sys.argv[3]
    p = plistlib.load(open(f, "rb"))
    set_gpu(p, gpu)
    plistlib.dump(p, open(f, "wb"))
elif action == "show":
    p = plistlib.load(open(sys.argv[2], "rb"))
    v = p.get("NVRAM", {}).get("Add", {}).get(GMUX, {}).get("gpu-power-prefs")
    gpu = {b"\x01\x00\x00\x00": "intel", b"\x00\x00\x00\x00": "radeon"}.get(v, "non impostata" if v is None else v.hex())
    print(f"SignalAppleOS={p['Booter']['Quirks'].get('SignalAppleOS')} gpu-power-prefs={gpu}")
PY
}

download_pkg() {   # scarica e verifica OpenCorePkg, stampa la cartella estratta
    local w="$1"
    command -v bsdtar >/dev/null || die "Serve bsdtar (pacman -S libarchive)."
    curl -sSfL "$OPENCORE_URL" -o "$w/oc.zip" || die "Download di OpenCore $OPENCORE_VERSION fallito."
    echo "$OPENCORE_SHA256  $w/oc.zip" | sha256sum -c --quiet - || die "SHA-256 di OpenCore diverso da quello fissato."
    mkdir -p "$w/pkg"
    bsdtar -xf "$w/oc.zip" -C "$w/pkg"
}

case "$CMD" in
config)
    [ -n "$PKG" ] && [ -n "$OUT" ] || die "Uso: opencore.sh config --pkg DIR --out FILE [--gpu intel|radeon]"
    plist generate "$PKG/Docs/Sample.plist" "$OUT" "${GPU:-radeon}"
    ok "Configurazione scritta in $OUT"
    ;;
status)
    ESP="$(find_esp || true)"
    [ "$(id -u)" = 0 ] || warn "Da utente la partizione EFI può non essere leggibile (Omarchy: /boot è solo di root): usa sudo/run0."
    echo "Partizione EFI: ${ESP:-non trovata (montata?)}"
    if [ -n "$ESP" ] && [ -f "$ESP/EFI/OC/config.plist" ]; then
        echo "OpenCore: $ESP/EFI/OC ($(plist show "$ESP/EFI/OC/config.plist"))"
    else
        echo "OpenCore: assente"
    fi
    if [ -r "$EFIVAR" ]; then
        echo "gpu-power-prefs nel firmware: $(od -An -tx1 -j4 "$EFIVAR" | tr -d ' ')  (01000000 = Intel)"
    else
        echo "gpu-power-prefs nel firmware: assente (Radeon)"
    fi
    for c in /sys/class/drm/card*-eDP-*; do
        [ -e "$c" ] || continue
        [ "$(cat "$c/status")" = connected ] || continue
        card="${c%%-*}"
        echo "Schermo interno: $(basename "$c") su $(basename "$(readlink -f "$card/device/driver")")"
    done
    command -v efibootmgr >/dev/null && efibootmgr | grep -E '^Boot(Current|Order)|OpenCore' || true
    ;;
gpu)
    [ "$GPU" = intel ] || [ "$GPU" = radeon ] || die "Uso: opencore.sh gpu intel|radeon"
    need_root
    ESP="$(find_esp || true)"
    [ -n "$ESP" ] && [ -f "$ESP/EFI/OC/config.plist" ] || die "OpenCore non trovato nella partizione EFI: prima sudo scripts/opencore.sh install"
    F="$ESP/EFI/OC/config.plist"
    run cp -a "$F" "$F.bak-$STAMP"
    if [ "$DRY_RUN" = 1 ]; then echo "[dry-run] gpu-power-prefs=$GPU e SignalAppleOS in $F"
    else plist gpu "$F" "$GPU"; fi
    ok "Schermo sulla $GPU dal prossimo avvio da OpenCore ($(plist show "$F"))."
    log "Riavvia passando da OpenCore; se lo schermo non cambia, riavvia una seconda volta (il firmware legge la variabile prima di OpenCore)."
    [ "$GPU" = intel ] && log "Indietro: sudo scripts/opencore.sh gpu radeon (o Option all'avvio → EFI Boot, oppure Reset NVRAM)."
    ;;
install)
    need_root
    command -v efibootmgr >/dev/null || die "Serve efibootmgr."
    ESP="$(find_esp || true)"
    [ -n "$ESP" ] || die "Partizione EFI con EFI/APPLE non trovata (montata su /boot o /boot/efi?)."
    OC="$ESP/EFI/OC"
    if [ -d "$OC" ] && [ "$REBUILD" = 0 ]; then
        ok "OpenCore già presente in $OC: lo lascio (--rebuild per rigenerarlo)."
    else
        [ -d "$OC" ] && run mv "$OC" "$ESP/EFI/OC.bak-$STAMP"
        if [ -n "$FROM" ]; then
            [ -f "$FROM/OpenCore.efi" ] && [ -f "$FROM/config.plist" ] || die "--from: $FROM non è una cartella EFI/OC (manca OpenCore.efi o config.plist)."
            log "Copio OpenCore da $FROM"
            run cp -r "$FROM" "$OC"
        else
            WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
            log "OpenCore $OPENCORE_VERSION (acidanthera), configurazione per Linux generata"
            download_pkg "$WORK"
            X="$WORK/pkg/X64/EFI/OC"
            run install -d "$OC/Drivers" "$OC/Tools"
            run install -m644 "$X/OpenCore.efi" "$OC/OpenCore.efi"
            for d in OpenRuntime.efi OpenLinuxBoot.efi ResetNvramEntry.efi; do run install -m644 "$X/Drivers/$d" "$OC/Drivers/$d"; done
            run install -m644 "$X/Tools/OpenShell.efi" "$OC/Tools/OpenShell.efi"
            if [ "$DRY_RUN" = 1 ]; then echo "[dry-run] genera $OC/config.plist da Docs/Sample.plist"
            else plist generate "$WORK/pkg/Docs/Sample.plist" "$OC/config.plist" "${GPU:-radeon}"; fi
        fi
        ok "OpenCore in $OC."
    fi
    # Voce di avvio. Con OpenCore già avviato (RequestBootVarRouting) le voci scritte da Linux finiscono nello spazio di
    # OpenCore; poco male: LauncherOption=Full fa sì che OpenCore registri e tenga per prima la propria voce.
    SRC="$(findmnt -rno SOURCE "$ESP")"
    DISK="/dev/$(lsblk -no PKNAME "$SRC")"; PARTN="$(cat "/sys/class/block/$(basename "$SRC")/partition")"
    if efibootmgr -v | grep -i 'OpenCore' | grep -qi "$(lsblk -no PARTUUID "$SRC")"; then
        ok "Voce di avvio OpenCore già presente per $SRC."
    else
        run efibootmgr -q -c -d "$DISK" -p "$PARTN" -L OpenCore -l '\EFI\OC\OpenCore.efi'
        ok "Voce di avvio OpenCore creata (prima nell'ordine). Le altre restano: Option all'avvio per sceglierle."
    fi
    [ -n "$GPU" ] && "$0" gpu "$GPU"
    ;;
*) die "Uso: opencore.sh status | install [--from DIR] [--rebuild] [--gpu intel|radeon] | gpu intel|radeon | config --pkg DIR --out FILE" ;;
esac
