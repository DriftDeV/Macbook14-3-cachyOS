"""Configurazione di OmaBar (renderer della Touch Bar che segue il tema di Omarchy, omabar/ e
omarchy/install-omabar.sh), senza Qt.

OmaBar parte da /usr/share/omabar/config.toml (predefinita, uguale a quella compilata dentro) e ogni sezione scritta in
/etc/omabar/config.toml ([display], [theme], tutti i [[layer]], [lock]) sostituisce quella predefinita per intero. Lo
rilegge da solo quando lo si salva (inotify). Un file non valido viene ignorato per intero: per questo prima di
salvare lo si fa controllare dal binario stesso (`omabar check`), che usa lo stesso parser del renderer.
install-omabar.sh rende il file scrivibile dall'utente.
"""
import copy
import glob
import os
import subprocess
import tempfile
import tomllib

from .tinydfr_keys import KEYS  # stesso enum Key di input-linux 0.7.1 (Cargo.lock di omabar)

BIN = "/usr/local/lib/macbookpro14-3/omabar/omabar"
UNIT = "macbookpro14-3-omabar.service"
SYS_CFG = "/usr/share/omabar/config.toml"
REPO_CFG = os.path.join(os.path.dirname(__file__), "..", "..", "omabar", "config.toml")
USER_CFG = "/etc/omabar/config.toml"
THEME = "/run/omabar/theme.toml"
ICON_DIRS = ["/etc/omabar/icons", "/usr/share/omabar/icons"]
BACKUP = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"),
                      "macbook-manager", "omabar.toml.bak")

SECTIONS = ["display", "theme", "layer", "lock"]
# Valori se manca anche il file predefinito (come Display/ThemeCfg::default in omarchy/omabar/src/config.rs).
DISPLAY = {"brightness": 255, "follow_screen": True, "min_brightness": 40, "pixel_shift": True,
           "font": "sans-serif", "font_size": 26, "fade_ms": 300}
THEME_CFG = {"path": THEME, "bar": "theme", "outlines": True}

# Faccia del tasto: una sola (validate in config.rs). "" = spazio vuoto.
KINDS = [("label", "Testo"), ("icon", "Icona"), ("clock", "Ora e data"), ("battery", "Batteria"),
         ("media", "Brano in riproduzione"), ("gap", "Separatore stretto"), ("", "Spazio vuoto")]
FACES = ("label", "icon", "clock", "battery", "media")
CLOCKS = ["%H:%M", "%H:%M  %a %-d", "%H:%M:%S", "%-d %b  %H:%M", "%a %-d %b", "%I:%M %p"]
FONTS = ["sans-serif", "sans-serif Bold", "monospace", "monospace Bold", "serif"]
COMMON_KEYS = ["Esc", "BrightnessDown", "BrightnessUp", "IllumDown", "IllumUp", "Mute", "VolumeDown", "VolumeUp",
               "MicMute", "PreviousSong", "PlayPause", "NextSong", "Search", "Scale", "Dashboard", "Print",
               "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
               "LeftMeta", "LeftCtrl", "LeftAlt", "LeftShift", "Delete", "Home", "End", "PageUp", "PageDown"]
ORDER = ["label", "icon", "icon_size", "icon_playing", "clock", "battery", "media", "gap", "keys", "width"]


def installed():
    return os.access(BIN, os.X_OK)


def writable():
    return os.access(USER_CFG, os.W_OK)


def _toml(path):
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        return {}


def defaults():
    raw = _toml(SYS_CFG) or _toml(REPO_CFG)
    d = {"display": dict(DISPLAY), "theme": dict(THEME_CFG), "layer": [], "lock": {"name": "bloccato", "buttons": []}}
    d["display"] = raw.get("display", d["display"])
    d["theme"] = raw.get("theme", d["theme"])
    d["layer"] = raw.get("layer", [])
    d["lock"] = raw.get("lock", d["lock"])
    return _fill(d)


def _fill(cfg):
    """Completa display e theme con i valori predefiniti (una sezione scritta a metà prende i default di serde)."""
    cfg["display"] = {**DISPLAY, **cfg["display"]}
    cfg["theme"] = {**THEME_CFG, **cfg["theme"]}
    return cfg


def load():
    """(configurazione effettiva, sezioni presenti in /etc). Solleva tomllib.TOMLDecodeError se /etc è illeggibile."""
    user = _toml(USER_CFG)
    cfg = defaults()
    for s in SECTIONS:
        if s in user:
            cfg[s] = copy.deepcopy(user[s])
    return _fill(cfg), set(user) & set(SECTIONS)


def icons():
    names = set()
    for d in ICON_DIRS + glob.glob("/usr/share/icons/Adwaita/symbolic/*"):
        for p in glob.glob(os.path.join(d, "*.svg")):
            names.add(os.path.splitext(os.path.basename(p))[0])
    return sorted(names)


def kind(button):
    for k in FACES:
        if button.get(k) not in (None, False):
            return k
    return "gap" if button.get("gap") else ""


def keys(button):
    return list(button.get("keys", []))


def validate(cfg):
    """Controlli veloci in Python (messaggi chiari); quello definitivo è check() con il binario."""
    errs = []
    d = cfg["display"]
    if not 1 <= d["min_brightness"] <= d["brightness"] <= 255:
        errs.append("Luminosità: minima e massima tra 1 e 255, la minima non sopra la massima.")
    if not cfg["layer"]:
        errs.append("Serve almeno un livello.")
    for name, layer in [("livello %d" % (i + 1), l) for i, l in enumerate(cfg["layer"])] + [("blocco", cfg["lock"])]:
        if not layer.get("buttons"):
            errs.append("%s: nessun tasto." % name)
        for j, b in enumerate(layer.get("buttons", [])):
            where = "%s, tasto %d" % (name, j + 1)
            bad = [k for k in keys(b) if k not in KEYS]
            if bad:
                errs.append("%s: tasto sconosciuto %s" % (where, ", ".join(bad)))
            if b.get("gap") and (kind(b) != "gap" or keys(b) or "width" in b):
                errs.append("%s: il separatore non ha faccia, tasti né larghezza." % where)
            if "width" in b and not 0.25 <= float(b["width"]) <= 20:
                errs.append("%s: larghezza tra 0.25 e 20." % where)
            if b.get("icon_playing") and not b.get("icon"):
                errs.append("%s: l'icona durante la riproduzione vuole anche l'icona." % where)
    return errs


# --- scrittura ---------------------------------------------------------------------------------------

def _q(s):
    return '"%s"' % str(s).replace("\\", "\\\\").replace('"', '\\"')


def _value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return ("%.2f" % v).rstrip("0").rstrip(".") if v != int(v) else "%d.0" % v
    if isinstance(v, list):
        return "[" + ", ".join(_value(x) for x in v) + "]"
    return _q(v)


def _button(b):
    parts = []
    for k in ORDER:
        if k not in b:
            continue
        v = b[k]
        if (k in ("battery", "media", "gap") and not v) or (k == "keys" and not v):
            continue
        parts.append("%s = %s" % (k, _value(v)))
    return "  { " + ", ".join(parts) + " }," if parts else "  {},"


def _table(name, data, keys_order):
    out = ["[%s]" % name]
    for k in keys_order:
        if k in data:
            out.append("%s = %s" % (k, _value(data[k])))
    return out


def _layer(header, layer):
    return [header, "name = %s" % _q(layer.get("name", "")), "buttons = ["] + \
        [_button(b) for b in layer.get("buttons", [])] + ["]"]


def dump(cfg):
    """Testo di /etc/omabar/config.toml: solo le sezioni che differiscono dalla configurazione predefinita."""
    base = defaults()
    out = ["# /etc/omabar/config.toml, scritto da MacBook Manager (scheda Touch Bar).",
           "# Ogni sezione qui sostituisce quella di /usr/share/omabar/config.toml; OmaBar lo rilegge da solo.", ""]
    if cfg["display"] != base["display"]:
        out += _table("display", cfg["display"], list(DISPLAY)) + [""]
    if cfg["theme"] != base["theme"]:
        out += _table("theme", cfg["theme"], list(THEME_CFG)) + [""]
    if cfg["layer"] != base["layer"]:
        for layer in cfg["layer"]:
            out += _layer("[[layer]]", layer) + [""]
    if cfg["lock"] != base["lock"]:
        out += _layer("[lock]", cfg["lock"]) + [""]
    return "\n".join(out).rstrip("\n") + "\n"


def _err(r, path):
    """Messaggio d'errore di omabar, senza il percorso temporaneo e senza l'elenco di tutti i tasti validi."""
    msg = (r.stderr or r.stdout).strip().replace(path, "config.toml")
    return msg.split(", expected one of")[0][:1500]


def _with_temp(text, fn):
    fd, path = tempfile.mkstemp(prefix="omabar-", suffix=".toml")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        return fn(path)
    finally:
        os.unlink(path)


def check(cfg):
    """None se OmaBar accetta la configurazione, altrimenti il suo messaggio d'errore."""
    if not installed():
        return None
    text = dump(cfg)

    def run(path):
        r = subprocess.run([BIN, "check", path], capture_output=True, text=True, timeout=10)
        return None if r.returncode == 0 else _err(r, path)
    return _with_temp(text, run)


def preview(cfg, out, layer=0, locked=False, media=None, theme=None):
    """Disegna la barra con questa configurazione (anche non salvata) in out (PNG). Restituisce l'errore o None."""
    if not installed():
        return "OmaBar non è installato"
    args = ["preview", out, "--layer", str(layer)]
    if locked:
        args.append("--locked")
    if media:
        args += ["--media", media]
    if theme or os.path.exists(THEME):
        args += ["--theme", theme or THEME]

    def run(path):
        r = subprocess.run([BIN] + args + ["--config", path], capture_output=True, text=True, timeout=10)
        return None if r.returncode == 0 else _err(r, path)
    return _with_temp(dump(cfg), run)


def save(cfg):
    errs = validate(cfg)
    if errs:
        raise ValueError("\n".join(errs))
    err = check(cfg)
    if err:
        raise ValueError(err)
    text = dump(cfg)
    tomllib.loads(text)
    try:
        old = open(USER_CFG, encoding="utf-8").read()
        os.makedirs(os.path.dirname(BACKUP), exist_ok=True)
        with open(BACKUP, "w", encoding="utf-8") as f:
            f.write(old)
    except OSError:
        pass
    # Scrittura sul posto (la cartella /etc/omabar non è dell'utente): OmaBar ricarica alla chiusura del file.
    with open(USER_CFG, "w", encoding="utf-8") as f:
        f.write(text)
    return text
