"""Configurazione di tiny-dfr (renderer alternativo della Touch Bar, scripts/install-tiny-dfr.sh), senza Qt.

tiny-dfr unisce /usr/share/tiny-dfr/config.toml (tutte le chiavi, da non toccare) e /etc/tiny-dfr/config.toml (solo ciò
che cambia) e rilegge il secondo appena lo si salva (inotify), senza riavvio. Un valore che non capisce (un nome di
tasto sbagliato, una chiave sconosciuta) gli fa scartare l'intero file, e un formato dell'ora non valido lo fa crollare:
per questo qui si scrivono solo valori controllati. install-tiny-dfr.sh rende il file scrivibile dall'utente.
"""
import glob
import os
import tomllib

from .tinydfr_keys import KEYS

SYS_CFG = "/usr/share/tiny-dfr/config.toml"
USER_CFG = "/etc/tiny-dfr/config.toml"
ICON_DIRS = ["/etc/tiny-dfr", "/usr/share/tiny-dfr"]
BACKUP = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"),
                      "macbook-manager", "tiny-dfr.toml.bak")

# (chiave, tipo, predefinito se manca anche il file di sistema)
SETTINGS = [
    ("MediaLayerDefault", bool, False),
    ("ShowButtonOutlines", bool, True),
    ("EnablePixelShift", bool, False),
    ("FontTemplate", str, ":bold"),
    ("AdaptiveBrightness", bool, True),
    ("ActiveBrightness", int, 128),
    ("DoublePressSwitchLayers", int, 0),
]
LAYERS = [("MediaLayerKeys", "Riga multimediale"), ("PrimaryLayerKeys", "Riga F1-F12")]
KINDS = [("Icon", "Icona"), ("Text", "Testo"), ("Time", "Ora e data"), ("Battery", "Batteria"), ("", "Spazio vuoto")]
TIME_FORMATS = [("24hr", "24 ore (14:05  mer 25 nov)"), ("12hr", "12 ore (2:05 PM  mer 25 nov)")]
BATTERY_MODES = [("icon", "icona"), ("percentage", "percentuale"), ("both", "icona e percentuale")]
FONTS = [(":bold", "Sans grassetto"), ("", "Sans normale"), ("monospace:bold", "Monospazio grassetto"),
         ("serif:bold", "Serif grassetto")]
MAX_BUTTONS = 24   # oltre, il disegno di tiny-dfr si rompe (commento nel file di sistema)
# Tasti più usati, per il menu (gli altri si scrivono a mano: devono stare in KEYS).
COMMON_KEYS = ["Esc", "BrightnessDown", "BrightnessUp", "IllumDown", "IllumUp", "Mute", "VolumeDown", "VolumeUp",
               "MicMute", "PreviousSong", "PlayPause", "NextSong", "Search", "Scale", "Dashboard", "Print",
               "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
               "LeftMeta", "LeftCtrl", "LeftAlt", "LeftShift", "Delete", "Home", "End", "PageUp", "PageDown"]

BUILTIN = {k: d for k, _t, d in SETTINGS}


def installed():
    return os.path.exists(SYS_CFG)


def writable():
    return os.access(USER_CFG, os.W_OK)


def _toml(path):
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        return {}


def defaults():
    d = dict(BUILTIN)
    d.update({k: v for k, v in _toml(SYS_CFG).items()})
    for key, _label in LAYERS:
        d.setdefault(key, [])
    return d


def load():
    """(configurazione effettiva, chiavi presenti in /etc). Solleva tomllib.TOMLDecodeError se /etc è illeggibile."""
    user = _toml(USER_CFG)
    cfg = defaults()
    cfg.update(user)
    for key, _label in LAYERS:
        cfg[key] = [dict(b) for b in cfg.get(key, [])]
    return cfg, set(user)


def icons():
    names = set()
    for d in ICON_DIRS:
        for p in glob.glob(os.path.join(d, "*.svg")) + glob.glob(os.path.join(d, "*.png")):
            names.add(os.path.splitext(os.path.basename(p))[0])
    return sorted(names)


def kind(button):
    for k, _label in KINDS:
        if k and k in button:
            return k
    return ""


def actions(button):
    a = button.get("Action", [])
    return [a] if isinstance(a, str) else list(a)


def validate(cfg):
    """Elenco di problemi (vuoto se il file si può scrivere)."""
    errs = []
    for key, typ, _d in SETTINGS:
        v = cfg.get(key)
        if not isinstance(v, typ) or (typ is int and isinstance(v, bool)):
            errs.append("%s: valore non valido (%r)" % (key, v))
    if isinstance(cfg.get("ActiveBrightness"), int) and not 0 <= cfg["ActiveBrightness"] <= 255:
        errs.append("ActiveBrightness deve stare tra 0 e 255")
    if isinstance(cfg.get("DoublePressSwitchLayers"), int) and not 0 <= cfg["DoublePressSwitchLayers"] <= 2000:
        errs.append("DoublePressSwitchLayers deve stare tra 0 e 2000 ms")
    names = set(icons())
    for key, label in LAYERS:
        btns = cfg.get(key, [])
        if not btns:
            errs.append("%s: serve almeno un pulsante" % label)
        if len(btns) > MAX_BUTTONS:
            errs.append("%s: al massimo %d pulsanti" % (label, MAX_BUTTONS))
        for i, b in enumerate(btns, 1):
            where = "%s, pulsante %d" % (label, i)
            kinds = [k for k, _l in KINDS if k and k in b]
            if len(kinds) > 1:
                errs.append("%s: un solo tipo tra icona, testo, ora e batteria" % where)
            k = kinds[0] if kinds else ""
            if k == "Icon" and "Theme" not in b and b["Icon"] not in names:
                errs.append("%s: icona \"%s\" non trovata in %s" % (where, b["Icon"], " o ".join(ICON_DIRS)))
            if k == "Text" and not str(b["Text"]).strip():
                errs.append("%s: testo vuoto" % where)
            if k == "Time" and b["Time"] not in [f for f, _l in TIME_FORMATS]:
                errs.append("%s: formato dell'ora non valido (tiny-dfr crollerebbe)" % where)
            if k == "Battery" and b["Battery"] not in [m for m, _l in BATTERY_MODES]:
                errs.append("%s: modo della batteria non valido" % where)
            for a in actions(b):
                if a not in KEYS:
                    errs.append("%s: tasto \"%s\" sconosciuto a tiny-dfr" % (where, a))
            s = b.get("Stretch", 1)
            if not isinstance(s, int) or isinstance(s, bool) or not 1 <= s <= 8:
                errs.append("%s: larghezza fra 1 e 8" % where)
            extra = set(b) - {"Icon", "Text", "Time", "Battery", "Action", "Stretch", "Theme", "Locale",
                              "IconWidth", "IconHeight"}
            if extra:
                errs.append("%s: campi sconosciuti %s" % (where, ", ".join(sorted(extra))))
    return errs


def _q(s):
    return '"%s"' % str(s).replace("\\", "\\\\").replace('"', '\\"')


def _value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, list):
        return "[" + ", ".join(_value(x) for x in v) + "]"
    return _q(v)


ORDER = ["Icon", "Text", "Time", "Battery", "Theme", "Locale", "IconWidth", "IconHeight", "Action", "Stretch"]


def _button(b):
    parts = []
    for k in ORDER:
        if k not in b:
            continue
        v = b[k]
        if k == "Action" and isinstance(v, list) and len(v) == 1:
            v = v[0]
        if k == "Stretch" and v == 1:
            continue
        parts.append("%s = %s" % (k, _value(v)))
    return "    { " + ", ".join(parts) + " }"


def dump(cfg):
    """Testo di /etc/tiny-dfr/config.toml: solo ciò che differisce dal file di sistema."""
    base = defaults()
    out = ["# /etc/tiny-dfr/config.toml, scritto da MacBook Manager (scheda Touch Bar).",
           "# Contiene solo ciò che cambia rispetto a /usr/share/tiny-dfr/config.toml; tiny-dfr lo rilegge da solo.", ""]
    for key, _t, _d in SETTINGS:
        if cfg.get(key) != base.get(key):
            out.append("%s = %s" % (key, _value(cfg[key])))
    for key, label in LAYERS:
        norm = [{k: v for k, v in b.items() if not (k == "Stretch" and v == 1)} for b in cfg[key]]
        if norm != base.get(key):
            out += ["", "# " + label, "%s = [" % key, ",\n".join(_button(b) for b in cfg[key]), "]"]
    return "\n".join(out) + "\n"


def save(cfg):
    errs = validate(cfg)
    if errs:
        raise ValueError("\n".join(errs))
    text = dump(cfg)
    tomllib.loads(text)  # deve rileggersi
    try:
        old = open(USER_CFG, encoding="utf-8").read()
        os.makedirs(os.path.dirname(BACKUP), exist_ok=True)
        with open(BACKUP, "w", encoding="utf-8") as f:
            f.write(old)
    except OSError:
        pass
    # Scrittura sul posto (la cartella /etc/tiny-dfr non è dell'utente): tiny-dfr ricarica alla chiusura del file.
    with open(USER_CFG, "w", encoding="utf-8") as f:
        f.write(text)
    return text
