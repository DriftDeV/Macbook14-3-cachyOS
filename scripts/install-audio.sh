#!/usr/bin/env bash
# Installa il driver Cirrus CS8409 (davidjo/snd_hda_macbookpro, fork dnlbtz).
# Rifiuta di procedere se il codec CS8409 non è rilevato: le fonti indicano
# CS8409 sul 14,3, ma NON è stato confermato sulla macchina reale.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=scripts/lib.sh
source "$SCRIPT_DIR/lib.sh"
# shellcheck source=config/sources.conf
source "$REPO_DIR/config/sources.conf"

[ "${1:-}" = "--dry-run" ] && DRY_RUN=1
need_root

if [ "$DRY_RUN" != 1 ]; then
    if ! has_cs8409 && [ "$FORCE" != 1 ]; then
        die "Codec CS8409 non rilevato (cerca 0x10138409 in /proc/asound/card*/codec#*). Usa FORCE=1 per ignorare."
    fi
    command -v git >/dev/null || die "git non installato."
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
log "Clono $AUDIO_REPO (ref $AUDIO_REF)"
run git clone --quiet --branch "$AUDIO_REF" --depth 1 "$AUDIO_REPO" "$WORK/snd"
if [ "$DRY_RUN" = 1 ]; then
    echo "[dry-run] (cd snd && ./install.cirrus.driver.sh -i)"
    exit 0
fi
cd "$WORK/snd"
[ -x ./install.cirrus.driver.sh ] || [ -f ./install.cirrus.driver.sh ] || die "install.cirrus.driver.sh non trovato nel fork."
# -i: installazione DKMS (come indicato dalle note di ricerca, non verificato qui).
bash ./install.cirrus.driver.sh -i
ok "Audio: driver installato. Riavvia, poi controlla: dmesg | grep -i cs8409"
warn "Bug noto 14,3: dopo alcuni boot il codec ha subsystem id 0x10138409 e non esce audio. Vedi docs/research-report.md."
warn "Il filter-chain PipeWire (dnlbtz/mbp143-audio) non è ancora integrato: vedi README."
