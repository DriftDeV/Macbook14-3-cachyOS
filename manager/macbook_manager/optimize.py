"""Ottimizzazione delle app Chromium/Electron e delle web app (scripts/fix-chromium-gpu.sh), senza Qt.

Correzione verificata il 24/11/2026 (docs/gpu.md): sotto Wayland il processo GPU di queste app crolla con i buffer tiled
della Radeon Polaris e l'accelerazione si spegne; AMD_DEBUG=notiling, dato solo a loro, lo evita (Brave, Discord, Sidra,
Claude Desktop provati). Lo script riconosce le app, le corregge e attiva un servizio che lo riapplica alle app nuove.
"""
import os
import re
import subprocess

from . import LIBDIR
from .status import chromium_gpu_processes

APPDIRS = ["/usr/share/applications", os.path.expanduser("~/.local/share/applications")]
SERVICE = "macbookpro14-3-chromium-x11.path"
LINE = re.compile(r"^(ok|NO)\s+(\S+\.desktop)(?:\s+\((.*)\))?$")


def script():
    """Percorso dello script: quello installato con il manager, quello della repo o la copia del servizio."""
    here = os.path.dirname(os.path.abspath(__file__))
    for p in (os.path.join(LIBDIR, "manager", "fix-chromium-gpu"),
              os.path.normpath(os.path.join(here, "..", "..", "scripts", "fix-chromium-gpu.sh")),
              os.path.expanduser("~/.local/lib/macbookpro14-3/fix-chromium-gpu")):
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def _desktop_info(fname):
    """(nome, è una web app) dal .desktop; la copia utente ha la precedenza."""
    for d in reversed(APPDIRS):
        p = os.path.join(d, fname)
        try:
            txt = open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        name = re.search(r"^Name=(.+)$", txt, re.M)
        exe = re.search(r"^Exec=(.+)$", txt, re.M)
        web = bool(exe and re.search(r"--app(-id)?=", exe.group(1)))
        return (name.group(1).strip() if name else fname[:-8]), web
    return fname[:-8], False


def apps():
    """Elenco delle app riconosciute: dict(file, name, web, ok, detail)."""
    s = script()
    if not s:
        return []
    out = subprocess.run([s, "--list"], capture_output=True, text=True, timeout=60).stdout
    res = []
    for line in out.splitlines():
        m = LINE.match(line.strip())
        if not m:
            continue
        name, web = _desktop_info(m.group(2))
        res.append({"file": m.group(2), "name": name, "web": web, "ok": m.group(1) == "ok", "detail": m.group(3) or ""})
    res.sort(key=lambda a: (a["ok"], a["web"], a["name"].lower()))
    return res


def service_active():
    return subprocess.run(["systemctl", "--user", "-q", "is-active", SERVICE]).returncode == 0


def running():
    """[(app, GPU attiva)] dei processi GPU Chromium/Electron in esecuzione (uno per app)."""
    seen = {}
    for app, acc, _x11 in chromium_gpu_processes():
        seen[app] = seen.get(app, True) and acc
    return sorted(seen.items())
