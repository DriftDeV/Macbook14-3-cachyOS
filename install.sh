#!/usr/bin/env bash
# Post-installazione per MacBookPro14,3 (15" 2017, Touch Bar T1) su CachyOS appena installato.
# Applica, nell'ordine, i passaggi provati su questa macchina (vedi README e docs/):
#   backup ESP Apple + firmware T1 -> pacchetti -> trackpad -> Touch Bar (modalità tastiera) -> audio ->
#   sospensione -> energia -> Bluetooth -> luminosità automatica -> [Touch Bar in modalità display] -> Wi-Fi
# Prima: sudo pacman -Syu e un riavvio (il kernel in uso deve essere quello installato).
#
#   sudo ./install.sh --dry-run          mostra cosa farebbe
#   sudo ./install.sh                    interattivo (chiede la modalità della Touch Bar)
#   sudo ./install.sh --yes --touchbar display --fnstrip
#   sudo ./install.sh --only audio,bluetooth      rifà solo alcuni passi (si può rilanciare)
set -euo pipefail
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib.sh
source "$REPO_DIR/scripts/lib.sh"

STEPS="backup packages input touchbar audio sleep power bluetooth brightness touchbar-display wifi"
LOG=/var/log/macbookpro14-3-install.log
TOUCHBAR_CHOICE=""      # keyboard | display
FNSTRIP=""              # yes | no
ONLY="" SKIP="" WIFI_FILE="" DO_INITRAMFS=0

ARGS="$*"   # per il registro: il ciclo sotto consuma gli argomenti

usage() {
    cat <<EOF
Uso: sudo ./install.sh [opzioni]
  --dry-run                 mostra cosa verrebbe fatto, senza modificare nulla
  --yes                     non chiedere niente (Touch Bar: keyboard, salvo --touchbar)
  --touchbar keyboard       Touch Bar con i tasti del firmware (come Boot Camp), predefinita
  --touchbar display        Touch Bar disegnata da T1Bridge (grafica, cursori, temi)
  --fnstrip | --no-fnstrip  con display: installa il renderer fnstrip (temi, grafici)
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
        --touchbar) TOUCHBAR_CHOICE="${2:-}"; shift ;;
        --fnstrip) FNSTRIP=yes ;;
        --no-fnstrip) FNSTRIP=no ;;
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
case "$TOUCHBAR_CHOICE" in ''|keyboard|display) ;; *) die "--touchbar vuole keyboard o display." ;; esac
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
curl -sfI --max-time 10 https://github.com >/dev/null || warn "Rete non raggiungibile: i passi che scaricano sorgenti falliranno."
[ "$(cat /sys/class/power_supply/ADP1/online 2>/dev/null)" = 1 ] || warn "Alimentatore non collegato: collegalo (compilazioni DKMS e Rust)."

# Esegue un comando come utente, con la sua sessione (systemctl --user, cargo).
as_user() {
    if [ "$DRY_RUN" = 1 ]; then echo "[dry-run] (come $USER_NAME) $*"; return 0; fi
    runuser -u "$USER_NAME" -- env HOME="$(getent passwd "$USER_NAME" | cut -d: -f6)" \
        XDG_RUNTIME_DIR="/run/user/$USER_UID" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$USER_UID/bus" "$@"
}

# ------------------------------------------------------------------ scelte
if wanted touchbar-display && [ -z "$TOUCHBAR_CHOICE" ]; then
    if [ "$ASSUME_YES" = 1 ] || [ ! -t 0 ]; then
        TOUCHBAR_CHOICE=keyboard
    else
        cat <<'EOF'

Modalità della Touch Bar:
  1) keyboard  tasti disegnati dal firmware del T1 (come in Boot Camp): Esc, F1-F12, luminosità,
               volume, media. La più provata: funziona anche dopo la sospensione e con ogni kernel.
  2) display   grafica di T1Bridge: cursori, temi, renderer personalizzati (fnstrip). La webcam passa
               in H.264 (Discord con "t1-webcam on"). Prima e dopo la sospensione passa da sola alla
               modalità tastiera. Richiede Rust e compila da sorgente (~5 minuti).
Si cambia in seguito con: sudo touchbar-mode set keyboard|display
EOF
        read -r -p "Scelta [1/2, predefinita 1]: " a
        case "$a" in 2|display) TOUCHBAR_CHOICE=display ;; *) TOUCHBAR_CHOICE=keyboard ;; esac
    fi
fi
[ -n "$TOUCHBAR_CHOICE" ] || TOUCHBAR_CHOICE=keyboard
if [ "$TOUCHBAR_CHOICE" = display ] && [ -z "$FNSTRIP" ]; then
    if [ "$ASSUME_YES" = 1 ] || [ ! -t 0 ]; then FNSTRIP=no
    else confirm "Installare anche fnstrip (temi, cursori, grafici di sistema sulla Touch Bar)?" && FNSTRIP=yes || FNSTRIP=no
    fi
fi
log "Touch Bar: $TOUCHBAR_CHOICE${FNSTRIP:+, fnstrip: $FNSTRIP}"

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
    if [ "$TOUCHBAR_CHOICE" = display ] && wanted touchbar-display; then
        pkgs+=(rust ffmpeg intel-media-driver brightnessctl)
        modinfo v4l2loopback >/dev/null 2>&1 || pkgs+=(v4l2loopback-dkms)
    fi
    for p in "${pkgs[@]}"; do
        if pacman -Si "$p" >/dev/null 2>&1 || pacman -Qi "$p" >/dev/null 2>&1; then avail+=("$p")
        else warn "pacchetto $p non trovato nei repository: salto"; fi
    done
    run pacman -S --needed --noconfirm "${avail[@]}"
    [ -d "/usr/lib/modules/$(uname -r)/build" ] || [ "$DRY_RUN" = 1 ] \
        || die "Header del kernel in uso ($(uname -r)) mancanti: aggiorna e riavvia (pacman -Syu)."
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
step_sleep() { sub install-sleep.sh; }
step_power() { sub install-power.sh; }
step_bluetooth() { sub install-bt.sh; }
step_brightness() { as_user bash "$REPO_DIR/scripts/set-kwin-brightness-curve.sh"; }

step_touchbar_display() {
    if [ "$TOUCHBAR_CHOICE" != display ]; then
        log "Modalità tastiera scelta: niente da installare (si può aggiungere dopo con install.sh --only touchbar-display --touchbar display)."
        return 0
    fi
    as_user bash "$REPO_DIR/scripts/build-t1bridge.sh"
    sub install-touchbar-display.sh
    if [ "$DRY_RUN" = 1 ]; then echo "[dry-run] TOUCHBAR_MODE=display in /etc/macbookpro14-3/touchbar.conf"
    else sed -i 's/^TOUCHBAR_MODE=.*/TOUCHBAR_MODE=display/' /etc/macbookpro14-3/touchbar.conf; fi
    if [ "$FNSTRIP" = yes ]; then as_user bash "$REPO_DIR/scripts/install-fnstrip.sh"; fi
    log "Modalità display salvata: parte al prossimo avvio."
}

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
run_step sleep "Sospensione (s2idle, Thunderbolt, NVMe)" step_sleep
run_step power "Energia (batteria/alimentatore)" step_power
run_step bluetooth "Bluetooth (audio delle chiamate)" step_bluetooth
run_step brightness "Luminosità automatica (curva KWin)" step_brightness
run_step touchbar-display "Touch Bar, modalità display (T1Bridge)" step_touchbar_display
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
Dopo il riavvio, controlli rapidi:
  dkms status                                   # appleibridge, snd_hda_macbookpro (+ t1bridge-* in modalità display)
  grep Subsystem /proc/asound/card*/codec#0     # 0x106b3900 = audio a posto
  iw dev wlan0 link                             # 5 GHz se il router li offre
  sudo touchbar-mode status                     # solo in modalità display
  scripts/sleep-test.sh check                   # sospensione configurata
EOF
