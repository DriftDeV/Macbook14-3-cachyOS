#!/usr/bin/env bash
# Imposta (una volta) la curva di luminosità automatica di KWin per lo schermo interno.
# Da utente, SENZA sudo. La curva viene scritta al prossimo login, prima che parta KWin.
#   scripts/set-kwin-brightness-curve.sh [file-curva.json]   (default: config/kde/kwin-brightness-curve.json)
#   scripts/set-kwin-brightness-curve.sh --undo
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=scripts/lib.sh
source "$SCRIPT_DIR/lib.sh"
[ "$(id -u)" -ne 0 ] || die "Lancialo come utente normale, non con sudo."

HELPER="$HOME/.local/share/macbookpro14-3/apply-kwin-brightness-curve.py"
UNIT="$HOME/.config/systemd/user/macbookpro14-3-kwin-curve.service"
CURVE="$HOME/.config/macbookpro14-3/kwin-brightness-curve.json"

if [ "${1:-}" = --undo ]; then
    systemctl --user disable macbookpro14-3-kwin-curve.service 2>/dev/null || true
    rm -f "$HELPER" "$UNIT" "$CURVE"
    systemctl --user daemon-reload
    ok "Rimosso. La curva già scritta resta in ~/.config/kwinoutputconfig.json (KWin la adatta alle tue regolazioni)."
    exit 0
fi

SRC="${1:-$REPO_DIR/config/kde/kwin-brightness-curve.json}"
python3 -I -c "import json,sys; c=json.load(open(sys.argv[1])); assert c and c==sorted(c) and all(len(p)==2 for p in c)" "$SRC" \
    || die "Curva non valida: serve una lista ordinata di coppie [lux, luminosità 0-1]."
install -Dm644 "$REPO_DIR/config/kde/apply-kwin-brightness-curve.py" "$HELPER"
install -Dm644 "$REPO_DIR/config/kde/macbookpro14-3-kwin-curve.service" "$UNIT"
install -Dm644 "$SRC" "$CURVE"
systemctl --user daemon-reload
systemctl --user enable macbookpro14-3-kwin-curve.service
ok "Curva pronta: verrà scritta al prossimo login (esci e rientra). Verifica: journalctl --user -u macbookpro14-3-kwin-curve"
