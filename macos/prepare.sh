#!/bin/bash
# Prepara l'avvio live/installazione di CachyOS dal disco interno del MacBookPro14,3,
# partendo da macOS e SENZA chiavetta USB.
#
# SPERIMENTALE: nessuna fonte documenta questa procedura end-to-end su un Mac Intel,
# e lo script non è stato eseguito su hardware reale. Ridimensionare APFS può
# comunque far perdere dati: FAI UN BACKUP TIME MACHINE PRIMA.
#
# Compatibile con bash 3.2 (quella di macOS).
#
# Uso:
#   ./macos/prepare.sh prepare --linux-gb 120            # DRY-RUN: stampa il piano
#   ./macos/prepare.sh prepare --linux-gb 120 --execute  # esegue davvero
#   ./macos/prepare.sh backup  --execute                 # solo backup mappa partizioni + ESP
#   ./macos/prepare.sh download --execute                # solo download+verifica ISO
#   ./macos/prepare.sh rollback --execute                # annulla (vedi sotto)
set -euo pipefail

EXECUTE=0
LINUX_GB=""
HELPER_GB=8
LABEL="COSLIVE"
CONTAINER=""
WORKDIR="$HOME/cachyos-mbp143"
ISO_VERSION=""
NOMODESET=0
NO_TARGET=0
BLESS_NEXT=0
LINUX_GPT_TYPE="0FC63DAF-8483-4772-8E79-3D69D8477DE4"   # "Linux filesystem"
FORCE=0
MIRROR="https://mirror.cachyos.org/ISO/desktop"
FALLBACK_VERSION="260809"   # ultima ISO confermata dalla ricerca (agosto 2026)

log()  { printf '\033[1;34m[*]\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m[ok]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

# Esegue (o stampa, in dry-run). Usare solo per comandi "semplici".
run() {
    if [ "$EXECUTE" = 1 ]; then "$@"; else printf '[dry-run] %s\n' "$*"; fi
}

usage() { sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; }

CMD="${1:-help}"
[ $# -gt 0 ] && shift
while [ $# -gt 0 ]; do
    case "$1" in
        --execute) EXECUTE=1 ;;
        --linux-gb) LINUX_GB="${2:-}"; shift ;;
        --helper-gb) HELPER_GB="${2:-}"; shift ;;
        --container) CONTAINER="${2:-}"; shift ;;
        --workdir) WORKDIR="${2:-}"; shift ;;
        --iso-version) ISO_VERSION="${2:-}"; shift ;;
        --nomodeset) NOMODESET=1 ;;
        --no-target) NO_TARGET=1 ;;
        --bless-next-boot) BLESS_NEXT=1 ;;
        --force) FORCE=1 ;;
        -h|--help) usage; exit 0 ;;
        *) die "Opzione sconosciuta: $1" ;;
    esac
    shift
done

[ "$(uname -s)" = "Darwin" ] || die "Questo script va eseguito su macOS."

# ---------------------------------------------------------------- preflight
preflight() {
    log "Controlli preliminari"
    local model
    model="$(sysctl -n hw.model)"
    if [ "$model" != "MacBookPro14,3" ]; then
        if [ "$FORCE" = 1 ]; then warn "Modello $model (atteso MacBookPro14,3): procedo per --force."
        else die "Modello $model: questo script è solo per MacBookPro14,3."; fi
    else ok "Modello $model"; fi

    if pmset -g batt | grep -q "AC Power"; then ok "Alimentatore collegato"
    elif [ "$EXECUTE" = 1 ]; then die "Collega l'alimentatore prima di toccare le partizioni."
    else warn "Alimentatore non collegato (obbligatorio con --execute)."; fi

    local fv
    fv="$(fdesetup status 2>/dev/null || true)"
    echo "    FileVault: $fv"
    case "$fv" in
        *"is On"*) warn "FileVault attivo: il ridimensionamento funziona solo con i volumi sbloccati. In caso di errore -69582 sblocca da Recovery." ;;
    esac
    echo "    SIP: $(csrutil status 2>/dev/null || echo sconosciuto)"

    if [ -z "$CONTAINER" ]; then
        CONTAINER="$(diskutil info -plist / | plutil -extract APFSContainerReference raw -o - - 2>/dev/null || true)"
    fi
    [ -n "$CONTAINER" ] || die "Container APFS non rilevato: passalo con --container diskN (vedi 'diskutil apfs list')."
    ok "Container APFS: $CONTAINER"
}

# ------------------------------------------------------------------- backup
do_backup() {
    local out
    out="$WORKDIR/backup-$(date +%Y%m%d-%H%M%S)"
    log "Backup mappa partizioni ed ESP in $out"
    run mkdir -p "$out"
    if [ "$EXECUTE" = 1 ]; then
        diskutil list > "$out/diskutil-list.txt"
        diskutil apfs list > "$out/diskutil-apfs-list.txt"
        local esp
        esp="$(diskutil list internal | awk '/EFI/ {print $NF; exit}')"
        [ -n "$esp" ] || die "ESP non trovata."
        log "Copio l'ESP ($esp), che contiene il firmware del chip T1 (serve sudo)"
        sudo dd if="/dev/r$esp" of="$out/esp.img" bs=1m
        shasum -a 256 "$out/esp.img" > "$out/esp.img.sha256"
        ok "Backup completato: $out"
    else
        echo "[dry-run] diskutil list/apfs list > $out ; sudo dd if=/dev/r<ESP> of=$out/esp.img"
    fi
}

# ----------------------------------------------------------------- download
latest_version() {
    local v
    v="$(curl -fsSL --max-time 20 "$MIRROR/" 2>/dev/null | grep -Eo 'href="[0-9]{6}/"' | grep -Eo '[0-9]{6}' | sort -n | tail -1 || true)"
    if [ -n "$v" ]; then echo "$v"; else warn "Impossibile leggere il mirror: uso $FALLBACK_VERSION" >&2; echo "$FALLBACK_VERSION"; fi
}

do_download() {
    [ -n "$ISO_VERSION" ] || ISO_VERSION="$(latest_version)"
    ISO_NAME="cachyos-desktop-linux-$ISO_VERSION.iso"
    ISO_PATH="$WORKDIR/$ISO_NAME"
    log "ISO: $ISO_NAME"
    run mkdir -p "$WORKDIR"
    if [ "$EXECUTE" != 1 ]; then
        echo "[dry-run] curl -C - -o $ISO_PATH $MIRROR/$ISO_VERSION/$ISO_NAME ; verifica sha256"
        return 0
    fi
    curl -fL -C - --retry 3 -o "$ISO_PATH" "$MIRROR/$ISO_VERSION/$ISO_NAME"
    curl -fsSL -o "$ISO_PATH.sha256" "$MIRROR/$ISO_VERSION/$ISO_NAME.sha256"
    local want got
    want="$(awk '{print $1; exit}' "$ISO_PATH.sha256")"
    got="$(shasum -a 256 "$ISO_PATH" | awk '{print $1}')"
    [ "$want" = "$got" ] || die "Checksum NON corrispondente (atteso $want, ottenuto $got). Cancella $ISO_PATH e riprova."
    ok "Checksum sha256 verificato"
    warn "La firma GPG (.iso.sig, chiave F3B607488DB35A47) non viene verificata da questo script: fallo a mano se vuoi."
}

# ---------------------------------------------------------------- partizioni
do_partition() {
    [ -n "$LINUX_GB" ] || die "Indica lo spazio totale per Linux: --linux-gb N"
    case "$LINUX_GB" in ''|*[!0-9]*) die "--linux-gb deve essere un intero." ;; esac
    [ "$LINUX_GB" -ge $((HELPER_GB + 40)) ] || die "--linux-gb troppo piccolo (minimo $((HELPER_GB + 40)): ${HELPER_GB} per il live + 40 per il sistema)."

    local total new
    total="$(diskutil info -plist "$CONTAINER" | plutil -extract TotalSize raw -o - -)"
    new=$((total - LINUX_GB * 1000 * 1000 * 1000))
    log "Container $CONTAINER: $((total / 1000000000)) GB -> $((new / 1000000000)) GB"
    log "Verrà creata la FAT32 '$LABEL' da ${HELPER_GB} GB; il resto ($((LINUX_GB - HELPER_GB)) GB) diventa la partizione Linux (vedi do_target)."
    echo "--- limiti validi (nessuna modifica) ---"
    diskutil apfs resizeContainer "$CONTAINER" limits || true
    echo "---"

    local snaps
    snaps="$(tmutil listlocalsnapshots / 2>/dev/null | grep -c 'com.apple' || true)"
    if [ "$snaps" -gt 0 ]; then
        warn "$snaps snapshot locali di Time Machine: possono causare l'errore -69531."
        if [ "$EXECUTE" = 1 ]; then
            printf "Eliminare gli snapshot locali (i backup su disco di Time Machine restano)? [y/N] "
            read -r a
            case "$a" in
                [Yy]*)
                    tmutil thinlocalsnapshots / 9999999999999 4 >/dev/null || true
                    echo "--- limiti dopo la rimozione degli snapshot ---"
                    diskutil apfs resizeContainer "$CONTAINER" limits || true
                    ;;
            esac
        else
            echo "[dry-run] tmutil thinlocalsnapshots / 9999999999999 4"
        fi
    fi

    echo
    echo "diskutil apfs resizeContainer $CONTAINER ${new}B fat32 $LABEL ${HELPER_GB}g"
    if [ "$EXECUTE" != 1 ]; then
        echo "[dry-run] Nessuna modifica. Rilancia con --execute per procedere."
        return 0
    fi
    warn "OPERAZIONE DISTRUTTIVA. Hai fatto il backup Time Machine?"
    printf "Scrivi RIDIMENSIONA per continuare: "
    read -r a
    [ "$a" = "RIDIMENSIONA" ] || die "Annullato."
    diskutil apfs resizeContainer "$CONTAINER" "${new}B" fat32 "$LABEL" "${HELPER_GB}g"
    ok "Partizione /Volumes/$LABEL creata"
}

# ------------------------------------------- partizione di destinazione Linux
# Crea, nello spazio libero dopo COSLIVE, una partizione "Linux filesystem" NON formattata
# (forma documentata di `diskutil addPartition ... %tipo% %noformat% 0`: size 0 = tutto lo spazio libero).
# In Calamares la selezioni e la formatti (ext4/btrfs) montandola su /.
do_target() {
    if [ "$NO_TARGET" = 1 ]; then
        log "--no-target: lascio lo spazio libero senza creare la partizione Linux."
        return 0
    fi
    local helper
    if [ "$EXECUTE" = 1 ]; then
        helper="$(diskutil info -plist "/Volumes/$LABEL" | plutil -extract DeviceIdentifier raw -o - -)"
        [ -n "$helper" ] || die "Partizione $LABEL non trovata."
        log "Creo la partizione di destinazione Linux dopo $helper (tutto lo spazio libero)"
        diskutil addPartition "$helper" "%$LINUX_GPT_TYPE%" %noformat% 0
        ok "Partizione Linux creata (non formattata)"
        diskutil list internal
    else
        echo "[dry-run] diskutil addPartition <ident-$LABEL> %$LINUX_GPT_TYPE% %noformat% 0"
    fi
}

# ------------------------------------------------------------------ estrazione
do_extract() {
    local dest="/Volumes/$LABEL" mnt
    if [ "$EXECUTE" != 1 ]; then
        echo "[dry-run] hdiutil attach -readonly ISO ; rsync -> $dest ; sed grub.cfg (archisosearchuuid -> archisolabel=$LABEL)"
        return 0
    fi
    [ -d "$dest" ] || die "$dest non montato."
    mnt="$(mktemp -d /tmp/cachyos-iso.XXXXXX)"
    log "Monto l'ISO"
    hdiutil attach -readonly -nobrowse -mountpoint "$mnt" "$ISO_PATH" >/dev/null
    trap 'hdiutil detach "$mnt" >/dev/null 2>&1 || true' EXIT

    if find "$mnt" -type f -size +4294967295c | grep -q .; then
        die "L'ISO contiene file > 4 GiB: non entrano in FAT32. Serve un altro metodo (vedi docs)."
    fi
    log "Copio i file (alcuni minuti)"
    rsync -rt "$mnt"/ "$dest"/ || cp -R "$mnt"/. "$dest"/

    log "Adatto grub.cfg: archisosearchuuid -> archisolabel=$LABEL"
    local f
    while IFS= read -r f; do
        sed -i '' -e "s/archisosearchuuid=[^ ]*/archisolabel=$LABEL/g" "$f"
        if [ "$NOMODESET" = 1 ]; then
            sed -i '' -e "s/archisolabel=$LABEL/archisolabel=$LABEL nomodeset/g" "$f"
        fi
        echo "    modificato: $f"
    done < <(find "$dest" -iname grub.cfg)

    if [ ! -f "$dest/EFI/BOOT/BOOTX64.EFI" ] && [ ! -f "$dest/EFI/BOOT/BOOTx64.EFI" ]; then
        warn "EFI/BOOT/BOOTX64.EFI non presente nell'ISO estratta."
        warn "Potrebbe stare dentro efiboot.img: estrailo a mano e copia la cartella EFI in $dest (vedi docs)."
    fi
    sync
    hdiutil detach "$mnt" >/dev/null 2>&1 || true
    trap - EXIT
    ok "ISO copiata e adattata"
}

final_instructions() {
    cat <<EOF

================ Prossimi passi ================
1. Riavvia tenendo premuto il tasto Option (⌥).
2. Scegli la voce "EFI Boot" corrispondente a $LABEL.
3. Se lo schermo resta nero, rifai la preparazione con --nomodeset.
4. Nel live, installa CachyOS con partizionamento MANUALE in Calamares:
   - seleziona la partizione "Linux filesystem" già creata (non formattata), formattala e montala su /;
   - monta la ESP di macOS (disk0s1) su /boot/efi SENZA formattarla: contiene il firmware T1;
   - la partizione COSLIVE (FAT32, 8 GB) puoi lasciarla o eliminarla a installazione finita.
   Come bootloader scegli rEFInd o GRUB (--removable): systemd-boot e Limine sono sconsigliati su EFI Apple.
5. Dopo l'installazione, da Linux:  sudo ./install.sh --dry-run   poi senza --dry-run.

Tastiera: se la tastiera interna non funziona nel live, usa una tastiera USB-C esterna.
Per tornare indietro:  ./macos/prepare.sh rollback --execute
EOF
}

# ------------------------------------------------------------------- rollback
do_rollback() {
    log "Rollback: elimino la partizione helper $LABEL e riespando macOS"
    local ident
    ident="$(diskutil info -plist "/Volumes/$LABEL" 2>/dev/null | plutil -extract DeviceIdentifier raw -o - - 2>/dev/null || true)"
    [ -n "$ident" ] || die "/Volumes/$LABEL non trovato (già rimosso o non montato?)."
    [ -n "$CONTAINER" ] || CONTAINER="$(diskutil info -plist / | plutil -extract APFSContainerReference raw -o - - 2>/dev/null || true)"
    [ -n "$CONTAINER" ] || die "Container non rilevato: usa --container."
    echo "diskutil eraseVolume 'Free Space' free $ident"
    echo "diskutil apfs resizeContainer $CONTAINER 0"
    warn "Le partizioni create dall'installazione di Linux NON vengono toccate: eliminale a mano da Utility Disco"
    warn "(solo quelle Linux!) prima del resize, altrimenti macOS non potrà riprendersi tutto lo spazio."
    if [ "$EXECUTE" != 1 ]; then echo "[dry-run] nessuna modifica."; return 0; fi
    printf "Scrivi ROLLBACK per continuare: "
    read -r a
    [ "$a" = "ROLLBACK" ] || die "Annullato."
    diskutil eraseVolume "Free Space" free "$ident"
    diskutil apfs resizeContainer "$CONTAINER" 0
    ok "Fatto. Se macOS non parte: tieni premuto Option e scegli Macintosh HD, oppure resetta la NVRAM (⌥⌘PR)."
}

# ----------------------------------------------------------------------- main
case "$CMD" in
    help|-h|--help) usage ;;
    backup)   preflight; do_backup ;;
    download) do_download ;;
    rollback) preflight; do_rollback ;;
    prepare)
        [ "$EXECUTE" = 1 ] || warn "DRY-RUN: non verrà modificato nulla. Usa --execute per eseguire."
        preflight
        do_backup
        do_download
        do_partition
        do_target
        do_extract
        if [ "$BLESS_NEXT" = 1 ]; then
            warn "bless --setBoot è inaffidabile con SIP/macOS recenti: in caso di errore usa il tasto Option."
            run sudo bless --mount "/Volumes/$LABEL" --file "/Volumes/$LABEL/EFI/BOOT/BOOTX64.EFI" --setBoot --nextonly
        fi
        final_instructions
        ;;
    *) usage; die "Comando sconosciuto: $CMD" ;;
esac
