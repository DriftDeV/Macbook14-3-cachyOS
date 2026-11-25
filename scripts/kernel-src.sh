#!/usr/bin/env bash
# Sorgenti del kernel per i moduli DKMS della repo: scarica da kernel.org i file di una cartella del kernel per la
# versione esatta del kernel di destinazione, così i moduli si compilano per qualsiasi kernel (CachyOS, Arch, Omarchy,
# LTS, aggiornamenti futuri) e non solo per la serie di cui la repo ha una copia.
#
#   kernel-src.sh <kernelver> <cartella-nel-kernel> <destinazione> [file...]
#     kernelver: come `uname -r` (7.3.5-2-cachyos, 6.18.60-3-cachyos-lts, 7.4.1-arch1-1, 7.4.0-1-omarchy...)
#     file: percorsi relativi alla cartella (anche in sottocartelle); senza, tutti i file della cartella
#   stampa su stdout il tag usato (es. v7.3.5); esce con 1 se non trova i file.
#
# Prova i tag vX.Y.Z e poi vX.Y (git stable di kernel.org, endpoint "plain", un file per richiesta). I file scaricati
# restano in /var/cache/macbookpro14-3/kernel-src/<tag>/ (KSRC_CACHE per cambiarla): una ricompilazione successiva,
# anche senza rete (per esempio nel hook DKMS di pacman), li ritrova lì. Copiato nelle cartelle DKMS dagli installer.
set -euo pipefail
kver="${1:?uso: kernel-src.sh <kernelver> <cartella> <destinazione> [file...]}"
dir="${2:?cartella}"
dest="${3:?destinazione}"
shift 3
BASE="https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/plain"
CACHE="${KSRC_CACHE:-/var/cache/macbookpro14-3/kernel-src}"

if [[ "$kver" =~ ^([0-9]+)\.([0-9]+)(\.([0-9]+))? ]]; then
    x="${BASH_REMATCH[1]}" y="${BASH_REMATCH[2]}" z="${BASH_REMATCH[4]:-0}"
else
    echo "kernel-src: versione del kernel non riconosciuta: $kver" >&2
    exit 1
fi
tags=()
[ "$z" != 0 ] && tags+=("v$x.$y.$z")
tags+=("v$x.$y")

fetch() {   # fetch <url> <file>: scarica in modo atomico; vero se riuscito
    local tmp="$2.part"
    mkdir -p "$(dirname "$2")"
    if curl -fsSL --retry 2 --connect-timeout 10 --max-time 60 -o "$tmp" "$1" 2>/dev/null; then
        mv -f "$tmp" "$2"
    else
        rm -f "$tmp"
        return 1
    fi
}

for tag in "${tags[@]}"; do
    c="$CACHE/$tag/$dir"
    files=("$@")
    if [ "${#files[@]}" -eq 0 ]; then   # tutti i file della cartella: elenco dalla pagina di kernel.org, poi in cache
        if [ ! -s "$c/.files" ]; then
            html="$(curl -fsSL --retry 2 --connect-timeout 10 --max-time 60 "$BASE/$dir/?h=$tag" 2>/dev/null)" || continue
            list="$(printf '%s' "$html" | grep -oE "plain/$dir/[^/?']+\\?h=" | sed -E "s#plain/$dir/##; s#\\?h=##" | sort -u)"
            [ -n "$list" ] || continue
            mkdir -p "$c"
            printf '%s\n' "$list" > "$c/.files"
        fi
        mapfile -t files < "$c/.files"
    fi
    ok=1
    for f in "${files[@]}"; do
        [ -s "$c/$f" ] && continue
        fetch "$BASE/$dir/$f?h=$tag" "$c/$f" || { ok=0; break; }
    done
    [ "$ok" = 1 ] || continue
    mkdir -p "$dest"
    for f in "${files[@]}"; do install -Dm644 "$c/$f" "$dest/$f"; done
    echo "$tag"
    exit 0
done
echo "kernel-src: sorgenti di $dir per $kver non trovati (tag ${tags[*]}; serve la rete la prima volta)" >&2
exit 1
