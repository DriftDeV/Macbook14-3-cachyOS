"""Configurazione di fnstrip (~/.config/fnstrip/config.toml): lettura, controllo e scrittura, senza Qt.

Il formato è il sottoinsieme di TOML descritto in fnstrip/config/default.toml (commit fissato in config/sources.conf):
chiavi in testa (theme, default_row, startup_animation, temperature_unit, debug_gestures), tabella [colors] facoltativa
e fino a 10 tabelle [[extras]] (icon, command, status, interface). Le chiavi sconosciute vengono conservate; i commenti
del file vengono rigenerati (la versione precedente resta in config.toml.bak).
"""
import os
import re
import shutil
import subprocess
import time
import tomllib

CONFIG = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "fnstrip", "config.toml")
BINARY = os.path.expanduser("~/.local/bin/fnstrip")
RENDERER_UNIT = "macbookpro14-3-touchbar-renderer.service"
MAX_EXTRAS = 10

THEMES = [("default", "Classico"), ("pastel", "Pastello"), ("mono", "Mono (grigi)"), ("rainbow", "Arcobaleno")]
# Preset = tema di fnstrip + [colors]. fnstrip conosce solo i quattro temi sopra: un preset si salva come
# theme = "<base>" più i suoi colori, e si riconosce rileggendo il file.
# OLED: sfondo e tasti neri, scritte e icone bianche, cursori grigio molto scuro. fnstrip disegna le icone con "label" anche sopra
# "fill" (cursori) e "lit" (tasti accesi): quei due restano grigio scuro, altrimenti le icone sparirebbero.
PRESETS = {
    "oled": ("OLED (tasti neri, alto contrasto)", "mono", {
        "background": "#000000", "plate": "#000000", "pressed": "#404040", "label": "#ffffff", "dim": "#707070",
        "lit": "#2e2e2e", "lit_pressed": "#4d4d4d", "fill": "#1a1a1a", "muted": "#101010"}),
}
ROWS = [("controls", "Comandi (luminosità, media, volume; F1-F12 tenendo Fn)"),
        ("function", "Esc + F1-F12 (comandi tenendo Fn)")]
UNITS = [("c", "°C"), ("f", "°F")]
COLORS = [("background", "Sfondo"), ("plate", "Tasto"), ("pressed", "Tasto premuto"), ("label", "Scritte"),
          ("dim", "Icone spente"), ("lit", "Tasto acceso"), ("lit_pressed", "Tasto acceso premuto"),
          ("fill", "Riempimento cursori"), ("muted", "Cursore muto")]
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

WEBCAM_STATUS = "systemctl --user -q is-active macbookpro14-3-webcam.service"
# icona -> (tipo, nome, descrizione, valori predefiniti)
ICONS = {
    "mic": ("toggle", "Microfono", "Acceso = microfono attivo (con lo spettro), barrato = muto.",
            {"command": "wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle",
             "status": "! wpctl get-volume @DEFAULT_AUDIO_SOURCE@ | grep -q MUTED"}),
    "camera": ("toggle", "Webcam virtuale", "Webcam per Discord e browser (t1-webcam): acceso = attiva, LED acceso.",
               {"command": "if %s; then t1-webcam off; else t1-webcam on; fi" % WEBCAM_STATUS, "status": WEBCAM_STATUS}),
    "vpn": ("toggle", "VPN", "Comando per accendere/spegnere, comando di stato (uscita 0 = accesa) e interfaccia "
                             "per il grafico del traffico. Esempi in fnstrip/config/default.toml.",
            {"command": "", "status": "", "interface": "wg0"}),
    "cpu": ("meter", "CPU", "Tempo utente (sotto) e di sistema.", {}),
    "mem": ("meter", "Memoria", "Memoria in uso (sotto) e cache.", {}),
    "disk": ("meter", "Disco", "Letture (sotto) e scritture al secondo.", {}),
    "net": ("meter", "Rete", "Byte ricevuti (sotto) e inviati al secondo. Interfaccia facoltativa (vuoto = tutte).",
            {"interface": ""}),
    "battery": ("meter", "Batteria", "Carica, fulmine con l'alimentatore, tempo residuo.", {}),
    "temp": ("meter", "Temperatura", "Temperatura del processore (coretemp).", {}),
    "fan": ("meter", "Ventole", "Giri delle due ventole (applesmc).", {}),
}
TOP_KEYS = ["theme", "default_row", "startup_animation", "temperature_unit", "debug_gestures"]


def preset_of(cfg):
    """Id del preset se tema e colori coincidono esattamente, altrimenti None."""
    for pid, (_label, base, colors) in PRESETS.items():
        if cfg.get("theme") == base and (cfg.get("colors") or {}) == colors:
            return pid
    return None


def apply_preset(cfg, pid):
    _label, base, colors = PRESETS[pid]
    cfg["theme"] = base
    cfg["colors"] = dict(colors)
    return cfg


def installed():
    return os.path.exists(BINARY)


def new_extra(icon):
    kind, _name, _desc, defaults = ICONS.get(icon, ("meter", icon, "", {}))
    return {"icon": icon, **{k: v for k, v in defaults.items() if v}}


def defaults():
    """La configurazione consigliata per questo Mac (quella provata il 23/11/2026)."""
    return {"theme": "mono", "default_row": "controls", "colors": {},
            "extras": [new_extra(i) for i in ("mic", "camera", "temp", "fan", "cpu", "battery")]}


def load(path=CONFIG):
    """Ritorna {theme, default_row, ..., colors: {}, extras: [..], _extra_keys: {...}}; senza file, i predefiniti."""
    if not os.path.exists(path):
        return defaults()
    with open(path, "rb") as f:
        data = tomllib.load(f)
    cfg = {k: v for k, v in data.items() if k not in ("colors", "extras")}
    cfg["colors"] = dict(data.get("colors") or {})
    cfg["extras"] = [dict(e) for e in data.get("extras") or [] if isinstance(e, dict)]
    return cfg


def validate(cfg):
    """Lista di problemi (in italiano); vuota se si può salvare."""
    errs = []
    if cfg.get("theme", "default") not in dict(THEMES):
        errs.append("Tema sconosciuto: %s" % cfg.get("theme"))
    for k, v in (cfg.get("colors") or {}).items():
        if not HEX.match(str(v)):
            errs.append("Colore %s non valido: %s (serve #rrggbb)" % (k, v))
    ex = cfg.get("extras") or []
    if len(ex) > MAX_EXTRAS:
        errs.append("La riga extra ha %d pulsanti: al massimo %d." % (len(ex), MAX_EXTRAS))
    for i, e in enumerate(ex, 1):
        if e.get("icon") == "vpn" and not (e.get("command") and e.get("status")):
            errs.append("Pulsante %d (VPN): servono il comando e il comando di stato." % i)
        for k, v in e.items():
            if "\n" in str(v):
                errs.append("Pulsante %d: %s su più righe non è ammesso." % (i, k))
    return errs


def _q(v):
    """Valore TOML: booleani così come sono, stringhe 'letterali' se contengono " e non ', altrimenti "base"."""
    if isinstance(v, bool):
        return "true" if v else "false"
    s = str(v)
    if '"' in s and "'" not in s:
        return "'%s'" % s
    return '"%s"' % s.replace("\\", "\\\\").replace('"', '\\"').replace("\t", "\\t")


def dumps(cfg):
    out = ["# Configurazione di fnstrip per il MacBookPro14,3 (Touch Bar in modalità display).",
           "# Scritta da MacBook Manager (%s); la versione precedente è in config.toml.bak." % time.strftime("%d/%m/%Y %H:%M"),
           "# Riferimento completo: ~/src/fnstrip/config/default.toml. Gli errori, con il numero di riga, in:",
           "#   journalctl --user -u %s" % RENDERER_UNIT, ""]
    for k in TOP_KEYS + sorted(k for k in cfg if k not in TOP_KEYS + ["colors", "extras"] and not k.startswith("_")):
        if k in cfg and cfg[k] not in (None, ""):
            out.append("%s = %s" % (k, _q(cfg[k])))
    colors = {k: v for k, v in (cfg.get("colors") or {}).items() if v}
    if colors:
        out += ["", "[colors]"] + ["%s = %s" % (k, _q(v)) for k, v in colors.items()]
    if cfg.get("extras"):
        out += ["", "# Riga extra: doppio tocco su Fn (resta finché non premi di nuovo Fn)."]
    for e in cfg.get("extras") or []:
        icon = e.get("icon", "")
        out += ["", "[[extras]]"]
        if icon in ICONS:
            out.append("# %s: %s" % (ICONS[icon][1], ICONS[icon][2]))
        out.append("icon = %s" % _q(icon))
        for k in ["command", "status", "interface"] + sorted(k for k in e if k not in ("icon", "command", "status", "interface")):
            if e.get(k) not in (None, ""):
                out.append("%s = %s" % (k, _q(e[k])))
    return "\n".join(out) + "\n"


def save(cfg, path=CONFIG):
    errs = validate(cfg)
    if errs:
        raise ValueError("\n".join(errs))
    text = dumps(cfg)
    tomllib.loads(text)  # deve rileggersi uguale
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        shutil.copy2(path, path + ".bak")
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(text)
    os.replace(tmp, path)
    return path


def renderer_active():
    return subprocess.run(["systemctl", "--user", "-q", "is-active", RENDERER_UNIT]).returncode == 0


def restart_renderer():
    """Riavvia il renderer se è attivo; ritorna (riavviato, righe di errore della configurazione)."""
    if not renderer_active():
        return False, []
    since = time.strftime("%Y-%m-%d %H:%M:%S")
    subprocess.run(["systemctl", "--user", "restart", RENDERER_UNIT])
    time.sleep(2)
    log = subprocess.run(["journalctl", "--user", "-u", RENDERER_UNIT, "--since", since, "--no-pager", "-q", "-o", "cat"],
                         capture_output=True, text=True).stdout
    return True, [l for l in log.splitlines() if re.search(r"config|line \d+|riga", l, re.I)]
