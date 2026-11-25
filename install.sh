#!/usr/bin/env bash
# Post-installazione per MacBookPro14,3 (15" 2017, Touch Bar T1) su CachyOS (o Arch/Omarchy) appena installato.
# Applica, nell'ordine, tutti i passaggi provati su questa macchina (vedi README e docs/), senza domande:
#   backup ESP Apple + firmware T1 -> pacchetti -> trackpad -> Touch Bar (modalità tastiera, usata in sospensione) ->
#   audio (driver) -> DSP degli altoparlanti (crossover, EQ, bassi bankstown) -> sospensione -> energia -> Bluetooth ->
#   Touch Bar in modalità display (T1Bridge, webcam H.264 corretta, renderer fnstrip) ->
#   renderer tiny-dfr (alternativo) -> Touch ID -> driver per i kernel futuri -> MacBook Manager -> app Chromium/Electron (GPU sotto Wayland) -> Wi-Fi
# La Touch Bar parte in modalità display con il renderer di T1Bridge: modalità (display/tastiera) e renderer
# (fnstrip/T1Bridge o tiny-dfr) si scelgono poi da MacBook Manager, scheda Touch Bar.
# Prima: sistema aggiornato (CachyOS/Arch: sudo pacman -Syu; Omarchy: omarchy update) e un riavvio, perché il kernel
# in uso deve essere quello installato. Funziona con KDE Plasma (provato) e con Hyprland/Omarchy (non provato sul 14,3).
#
#   sudo ./install.sh --dry-run                  mostra cosa farebbe
#   sudo ./install.sh                            installa tutto
#   sudo ./install.sh --only audio,audio-dsp     rifà solo alcuni passi (si può rilanciare)
set -euo pipefail
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib.sh
source "$REPO_DIR/scripts/lib.sh"

STEPS="backup packages input touchbar audio audio-dsp sleep power bluetooth touchbar-display tiny-dfr touchid kernel manager apps wifi"
LOG=/var/log/macbookpro14-3-install.log
ONLY="" SKIP="" WIFI_FILE="" DO_INITRAMFS=0

ARGS="$*"   # per il registro: il ciclo sotto consuma gli argomenti

usage() {
    cat <<EOF
Uso: sudo ./install.sh [opzioni]
  --dry-run                 mostra cosa verrebbe fatto, senza modificare nulla
  --yes                     non chiedere conferme
  --only PASSI              solo questi passi (separati da virgole)
  --skip PASSI              salta questi passi
  --wifi-nvram FILE         usa un file NVRAM tuo invece di generarlo dal chip
  --initramfs               (non provato) tastiera SPI nell'initramfs, utile solo con disco cifrato
  --force                   ignora il controllo del modello (sconsigliato)
  --list                    elenca i passi
Passi: $STEPS
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=1 ;;
        --yes) ASSUME_YES=1 ;;
        --force) FORCE=1 ;;
        --touchbar|--fnstrip|--no-fnstrip)
            die "$1 non esiste più: si installa tutto e modalità e renderer si scelgono da MacBook Manager." ;;
        --only) ONLY="${2:-}"; shift ;;
        --skip) SKIP="${2:-}"; shift ;;
        --wifi-nvram) WIFI_FILE="${2:-}"; shift ;;
        --initramfs) DO_INITRAMFS=1 ;;
        --list) echo "$STEPS"; exit 0 ;;
        -h|--help) usage; exit 0 ;;
        *) usage; die "Opzione sconosciuta: $1" ;;
    esac
    shift
done
export DRY_RUN ASSUME_YES FORCE

wanted() {   # il passo $1 va eseguito?
    local s=",$1,"
    if [ -n "$ONLY" ] && [[ ",$ONLY," != *"$s"* ]]; then return 1; fi
    if [ -n "$SKIP" ] && [[ ",$SKIP," == *"$s"* ]]; then return 1; fi
    return 0
}

# ------------------------------------------------------------------ controlli preliminari
need_root
check_model
command -v pacman >/dev/null || die "pacman non trovato: serve CachyOS/Arch."
USER_NAME="${SUDO_USER:-}"
[ -n "$USER_NAME" ] && [ "$USER_NAME" != root ] || [ "$DRY_RUN" = 1 ] \
    || die "Lancialo con sudo dal tuo utente (serve per i passi da utente: luminosità, renderer)."
[ -n "$USER_NAME" ] || USER_NAME="$(id -un)"
USER_UID="$(id -u "$USER_NAME")"
[ -d "/usr/lib/modules/$(uname -r)" ] \
    || die "Il kernel in uso ($(uname -r)) non è più installato: dopo l'aggiornamento serve un riavvio."
if [ "$DRY_RUN" != 1 ]; then
    exec > >(tee -a "$LOG") 2>&1
    echo "===== $(date -Is) install.sh $ARGS (utente $USER_NAME, kernel $(uname -r))"
fi
DESKTOP="$(desktop_kind)"
log "Desktop: $DESKTOP$(is_omarchy && echo ' (Omarchy)')"
[ "$DESKTOP" = kde ] || warn "Desktop diverso da KDE Plasma: provato solo su KDE. Su Hyprland/Omarchy vedi README, sezione Omarchy."
curl -sfI --max-time 10 https://github.com >/dev/null || warn "Rete non raggiungibile: i passi che scaricano sorgenti falliranno."
[ "$(cat /sys/class/power_supply/ADP1/online 2>/dev/null)" = 1 ] || warn "Alimentatore non collegato: collegalo (compilazioni DKMS e Rust)."

# Esegue un comando come utente, con la sua sessione (systemctl --user, cargo).
as_user() {
    if [ "$DRY_RUN" = 1 ]; then echo "[dry-run] (come $USER_NAME) $*"; return 0; fi
    runuser -u "$USER_NAME" -- env HOME="$(getent passwd "$USER_NAME" | cut -d: -f6)" \
        XDG_RUNTIME_DIR="/run/user/$USER_UID" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$USER_UID/bus" "$@"
}

# ------------------------------------------------------------------ esecuzione dei passi
declare -A RESULT
ORDER=()
FATAL_STEPS=" backup packages "
run_step() {   # run_step nome descrizione funzione
    local name="$1" desc="$2" fn="$3"
    ORDER+=("$name")
    if ! wanted "$name"; then RESULT[$name]="saltato"; return 0; fi
    log "==================== $desc"
    # Fuori da un "if": dentro una condizione bash ignorerebbe set -e e un passo fallito a metà sembrerebbe riuscito.
    local rc
    set +e
    ( set -e; "$fn" )
    rc=$?
    set -e
    if [ "$rc" = 0 ]; then
        RESULT[$name]="ok"
    else
        RESULT[$name]="ERRORE"
        warn "Passo '$name' non riuscito (dettagli sopra e in $LOG)."
        if [[ "$FATAL_STEPS" == *" $name "* ]]; then summary; die "Passo indispensabile: mi fermo."; fi
    fi
}
sub() {   # sub script.sh [argomenti]: --dry-run va per primo (alcuni script guardano solo $1)
    local s="$1"; shift
    if [ "$DRY_RUN" = 1 ]; then bash "$REPO_DIR/scripts/$s" --dry-run "$@"; else bash "$REPO_DIR/scripts/$s" "$@"; fi
}

step_backup() { bash "$REPO_DIR/scripts/backup-esp.sh"; }

step_packages() {
    local pkgs headers p avail=()
    headers="$(kernel_header_packages | tr '\n' ' ')"
    [ -n "$headers" ] || warn "Nessun pacchetto header individuato: i moduli DKMS non compileranno."
    # shellcheck disable=SC2206
    pkgs=(base-devel dkms git curl zstd python patch iw networkmanager iio-sensor-proxy
          linux-firmware linux-firmware-broadcom libinput-tools $headers)
    wanted manager && pkgs+=(pyside6)   # GUI di MacBook Manager
    # Modalità display (T1Bridge, fnstrip, tiny-dfr), webcam H.264 decodificata dalla Intel, DSP audio.
    pkgs+=(rust ffmpeg intel-media-driver brightnessctl cairo librsvg freetype2 fontconfig pipewire-audio wireplumber)
    modinfo v4l2loopback >/dev/null 2>&1 || pkgs+=(v4l2loopback-dkms)
    # Scheda Batteria (cronologia di UPower) e profili energetici (regole della scheda CPU): su KDE ci sono già.
    pkgs+=(upower power-profiles-daemon)
    # Hyprland/Omarchy: serve un agente polkit per le password del manager (KDE ha il suo).
    if [ "$DESKTOP" = hyprland ] && ! pacman -Qq 2>/dev/null \
            | grep -qxE 'hyprpolkitagent|polkit-gnome|polkit-kde-agent|lxqt-policykit|mate-polkit|polkit-mate'; then
        pkgs+=(hyprpolkitagent)
    fi
    for p in "${pkgs[@]}"; do
        if pacman -Si "$p" >/dev/null 2>&1 || pacman -Qi "$p" >/dev/null 2>&1; then avail+=("$p")
        else warn "pacchetto $p non trovato nei repository: salto"; fi
    done
    run pacman -S --needed --noconfirm "${avail[@]}"
    run systemctl enable --now upower.service power-profiles-daemon.service 2>/dev/null || true
    if [ "$DESKTOP" = hyprland ] && pacman -Q hyprpolkitagent >/dev/null 2>&1; then
        as_user systemctl --user enable hyprpolkitagent.service || true
    fi
    [ -d "/usr/lib/modules/$(uname -r)/build" ] || [ "$DRY_RUN" = 1 ] \
        || die "Header del kernel in uso ($(uname -r)) mancanti: aggiorna e riavvia ($(is_omarchy && echo 'omarchy update' || echo 'sudo pacman -Syu'))."
}

step_input() {
    install_file 644 "$REPO_DIR/config/libinput/local-overrides.quirks" /etc/libinput/local-overrides.quirks
    if [ "$DO_INITRAMFS" = 1 ]; then
        install_file 644 "$REPO_DIR/config/mkinitcpio/macbookpro14-3.conf" /etc/mkinitcpio.conf.d/macbookpro14-3.conf
        run mkinitcpio -P
    fi
}
step_touchbar() { sub install-touchbar.sh; }
step_audio() { sub install-audio.sh; }
step_audio_dsp() { sub install-audio-dsp.sh; }
step_sleep() { sub install-sleep.sh; }
step_power() { sub install-power.sh; }
step_bluetooth() { sub install-bt.sh; }
step_manager() { sub install-manager.sh; }

# Driver DKMS per i kernel futuri: ogni modulo si ricompila da solo agli aggiornamenti (hook di pacman, sorgenti del
# kernel esatto da kernel.org); in più all'avvio ricompila quelli rimasti indietro (per esempio aggiornamento senza rete).
step_kernel() {
    install_file 755 "$REPO_DIR/config/dkms-catchup.sh" /usr/local/lib/macbookpro14-3/dkms-catchup.sh
    install_file 644 "$REPO_DIR/config/systemd/macbookpro14-3-dkms-catchup.service" \
        /etc/systemd/system/macbookpro14-3-dkms-catchup.service
    run systemctl daemon-reload
    run systemctl enable macbookpro14-3-dkms-catchup.service
    # Pulizia: la curva di luminosità automatica di KWin non fa più parte della repo.
    local h; h="$(getent passwd "$USER_NAME" | cut -d: -f6)"
    if [ -e "$h/.config/systemd/user/macbookpro14-3-kwin-curve.service" ]; then
        as_user systemctl --user disable macbookpro14-3-kwin-curve.service || true
        run rm -f "$h/.config/systemd/user/macbookpro14-3-kwin-curve.service" \
            "$h/.local/share/macbookpro14-3/apply-kwin-brightness-curve.py"
    fi
}

step_touchbar_display() {
    as_user bash "$REPO_DIR/scripts/build-t1bridge.sh"
    sub install-touchbar-display.sh
    if [ "$DRY_RUN" = 1 ]; then echo "[dry-run] TOUCHBAR_MODE=display in /etc/macbookpro14-3/touchbar.conf"
    else sed -i 's/^TOUCHBAR_MODE=.*/TOUCHBAR_MODE=display/' /etc/macbookpro14-3/touchbar.conf; fi
    as_user bash "$REPO_DIR/scripts/install-fnstrip.sh"
    log "Modalità display salvata (renderer fnstrip): parte al prossimo avvio."
}

# tiny-dfr resta installato ma non attivo: si sceglie da MacBook Manager (Touch Bar > Renderer).
step_tiny_dfr() { sub install-tiny-dfr.sh; }

step_touchid() { sub install-touchid.sh; }

step_apps() { as_user bash "$REPO_DIR/scripts/fix-chromium-gpu.sh"; }

step_wifi() {
    if [ -n "$WIFI_FILE" ]; then
        sub install-wifi-nvram.sh --file "$WIFI_FILE"
    else
        sub install-wifi.sh
    fi
    [ "$DRY_RUN" = 1 ] && return 0
    log "Attendo che la rete torni (fino a 60 s)..."
    for _ in $(seq 30); do
        nmcli -t -f STATE general 2>/dev/null | grep -q '^connected' && { ok "Rete di nuovo connessa."; return 0; }
        sleep 2
    done
    warn "La rete non è ancora tornata: ricollegati dal pannello di KDE."
}

summary() {
    local n
    echo
    log "==================== Riepilogo"
    for n in "${ORDER[@]}"; do printf '  %-17s %s\n' "$n" "${RESULT[$n]}"; done
    [ "$DRY_RUN" = 1 ] || echo "  registro: $LOG"
}

run_step backup "Backup ESP Apple e firmware T1" step_backup
run_step packages "Pacchetti" step_packages
run_step input "Trackpad (quirk libinput)" step_input
run_step touchbar "Touch Bar, modalità tastiera (apple-ibridge, DKMS)" step_touchbar
run_step audio "Audio CS8409 (DKMS)" step_audio
run_step audio-dsp "DSP degli altoparlanti (mbp143-audio + bankstown)" step_audio_dsp
run_step sleep "Sospensione (S3, Thunderbolt, NVMe)" step_sleep
run_step power "Energia (batteria/alimentatore)" step_power
run_step bluetooth "Bluetooth (audio delle chiamate)" step_bluetooth
run_step touchbar-display "Touch Bar, modalità display (T1Bridge, webcam, fnstrip)" step_touchbar_display
run_step tiny-dfr "Touch Bar, renderer alternativo tiny-dfr" step_tiny_dfr
run_step touchid "Touch ID (T1Bridge: rete privata, xART, broker, fprintd)" step_touchid
run_step kernel "Driver per i kernel futuri (ricompilazione automatica)" step_kernel
run_step manager "MacBook Manager (stato e azioni rapide, GUI)" step_manager
run_step apps "App Chromium/Electron: GPU Radeon sotto Wayland (AMD_DEBUG=notiling)" step_apps
run_step wifi "Wi-Fi 5 GHz (NVRAM dal chip)" step_wifi

summary
failed=""
for n in "${ORDER[@]}"; do [ "${RESULT[$n]}" = ERRORE ] && failed="$failed $n"; done
if [ -n "$failed" ]; then
    warn "Non riusciti:$failed. Il resto è applicato; puoi rifarli con: sudo ./install.sh --only $(echo "$failed" | sed 's/^ //; s/ /,/g')"
    exit 2
fi
ok "Fatto. Ora SPEGNI completamente il Mac, aspetta ~30 s e riaccendi (il T1 riparte pulito)."
cat <<'EOF'
Dopo la riaccensione:
  1. Apri "MacBook Manager" dal menu (o l'icona nella barra di sistema): stato di tutto, azioni rapide,
     scheda Touch Bar per scegliere modalità (display/tastiera) e renderer (fnstrip/T1Bridge o tiny-dfr).
  2. Touch ID: sudo scripts/install-touchid.sh import, poi registra un dito (MacBook Manager > Azioni > Registra
     un'impronta, o fprintd-enroll; su KDE anche Impostazioni di sistema > Utenti). La prima volta può fallire: riprova.
     Su Omarchy NON usare il suo menu Setup > Security > Fingerprint: installerebbe il fprintd normale al posto di
     quello per il T1.
  3. Controlli da terminale, se servono:
       macbook-manager status                        tutto in una schermata
       grep Subsystem /proc/asound/card*/codec#0     0x106b3900 = audio a posto
       wpctl status | grep "MacBook Pro 14,3"        DSP degli altoparlanti e del microfono attivi
       sudo touchbar-mode status                     modalità e renderer della Touch Bar
       iw dev wlan0 link                             5 GHz se il router li offre
EOF
if [ "$DESKTOP" = hyprland ]; then
    cat <<'EOF'
Hyprland/Omarchy: icona del manager, renderer della Touch Bar e limite FPS partono con la sessione di systemd (uwsm).
Se la tua sessione non usa uwsm, aggiungi l'avvio di "macbook-manager gui --tray" (su Omarchy in
~/.config/hypr/autostart.lua) e controlla con: systemctl --user status macbookpro14-3-touchbar-renderer
EOF
fi
