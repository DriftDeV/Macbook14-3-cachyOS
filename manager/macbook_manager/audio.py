"""Preset e personalizzazioni del DSP degli altoparlanti (pkgs/mbp143-audio + pkgs/bankstown-lv2), senza Qt.

Le impostazioni agiscono solo su controlli sicuri del grafo "MacBook Pro 14,3 Speakers":
  - bankstown (bassi psicoacustici): acceso/spento, intensità, frequenza, carattere;
  - livello massimo e bilanciamento: guadagno f6 (dopo compressori ed EQ, prima del crossover) che può solo SCENDERE
    sotto il valore di fabbrica (1,188502 = +1,5 dB), mai salire;
  - compensazione dei bassi a basso volume (Loudness) e compressione dinamica (Mozart, DualBand): accese/spente.
Restano sempre attivi, e qui non si toccano, crossover, EQ di Apple, BuzzKill, limitatori ControlFreak e protezione
termica. Ogni valore è limitato qui e di nuovo nello script di WirePlumber (config/wireplumber/macbook-manager-audio.lua),
che riapplica le impostazioni salvate ogni volta che il filtro rinasce (riavvio, cuffie scollegate, nuovo accesso).

Le impostazioni stanno in ~/.local/state/wireplumber/macbook-manager-audio (file di stato di WirePlumber, formato ini).
"""
import json
import math
import os
import shutil
import subprocess

NODE = "audio_effect.mbp143-speakers"
STATE = os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"),
                     "wireplumber", "macbook-manager-audio")
GROUP = "macbook-manager-audio"
F6_FACTORY = 1.188502  # guadagno f6 del grafo di fabbrica (+1,5 dB)

# Limiti delle personalizzazioni (gli stessi, sui parametri del grafo, sono nello script Lua).
AMOUNT = (0.5, 2.5)     # bankstown "amt": Asahi usa 1,45 (MBP 14") e 1,65 (MBP 16"); il plugin arriva a 15
FREQ = (100, 250)       # Hz: banda da cui nascono le armoniche (ceil) e taglio finale (final_hp)
CHARACTER = (0.0, 1.0)  # bankstown "blend": 0 = più 2ª armonica (morbido), 1 = solo 3ª (deciso)
LEVEL_DB = (-12.0, 0.0)  # livello massimo rispetto alla fabbrica: solo attenuazione
BALANCE = (-100, 100)   # -100 = tutto a sinistra (destra -12 dB), +100 = tutto a destra (sinistra -12 dB)
BALANCE_MAX_DB = 12.0

DEFAULTS = {
    "bass": True, "bass_amount": 1.45, "bass_freq": 200, "bass_character": 0.67,
    "sat_second": 1.35, "sat_third": 2.25,
    "level_db": 0.0, "balance": 0, "loudness": True, "compression": True,
}
PRESETS = [
    ("factory", "DSP di fabbrica",
     "Solo l'elaborazione di Apple: crossover tweeter/woofer, equalizzazione, compressori, limitatori e protezione "
     "termica. Niente bassi aggiunti.",
     dict(DEFAULTS, bass=False)),
    ("bass", "DSP + bassi (consigliato)",
     "L'elaborazione di Apple più i bassi psicoacustici di Asahi Linux (bankstown, valori del MacBook Pro 14\"): "
     "armoniche dei bassi che i piccoli altoparlanti riproducono bene, senza far lavorare di più i woofer.",
     dict(DEFAULTS)),
    ("bass-strong", "DSP + bassi intensi",
     "Come sopra con i valori di Asahi per il MacBook Pro 16\": armoniche più forti, nate più in basso (125 Hz).",
     dict(DEFAULTS, bass_amount=1.65, bass_freq=125, bass_character=1.0, sat_second=1.05, sat_third=1.85)),
    ("night", "Volume basso / notte",
     "Bassi accesi, livello massimo ridotto di 6 dB: utile di notte o con altoparlanti che distorcono ad alto volume.",
     dict(DEFAULTS, level_db=-6.0)),
]
BY_PRESET = {p[0]: p for p in PRESETS}


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def sanitize(s):
    """Copia di s con tutti i campi presenti e dentro i limiti."""
    out = dict(DEFAULTS)
    out.update({k: s[k] for k in DEFAULTS if k in s})
    out["bass"] = bool(out["bass"])
    out["loudness"] = bool(out["loudness"])
    out["compression"] = bool(out["compression"])
    out["bass_amount"] = round(clamp(float(out["bass_amount"]), *AMOUNT), 2)
    out["bass_freq"] = int(clamp(int(out["bass_freq"]), *FREQ))
    out["bass_character"] = round(clamp(float(out["bass_character"]), *CHARACTER), 2)
    out["sat_second"] = round(clamp(float(out["sat_second"]), 0.0, 3.0), 2)
    out["sat_third"] = round(clamp(float(out["sat_third"]), 0.0, 3.0), 2)
    out["level_db"] = round(clamp(float(out["level_db"]), *LEVEL_DB), 1)
    out["balance"] = int(clamp(int(out["balance"]), *BALANCE))
    return out


def preset_of(s):
    """Id del preset che coincide con s, oppure "custom"."""
    s = sanitize(s)
    for pid, _n, _d, vals in PRESETS:
        if sanitize(vals) == s:
            return pid
    return "custom"


def params(s):
    """Parametri del grafo (nome del controllo -> valore) per le impostazioni s."""
    s = sanitize(s)
    level = 10 ** (s["level_db"] / 20)
    b = s["balance"] / 100.0
    left = 10 ** (-max(b, 0) * BALANCE_MAX_DB / 20)
    right = 10 ** (-max(-b, 0) * BALANCE_MAX_DB / 20)
    return {
        "bassex:bypass": 0.0 if s["bass"] else 1.0,
        "bassex:amt": s["bass_amount"],
        "bassex:ceil": float(s["bass_freq"]),
        "bassex:final_hp": float(s["bass_freq"]),
        "bassex:blend": s["bass_character"],
        "bassex:sat_second": s["sat_second"],
        "bassex:sat_third": s["sat_third"],
        "f6c0gain:Mult": round(F6_FACTORY * level * left, 6),
        "f6c1gain:Mult": round(F6_FACTORY * level * right, 6),
        "f2loudness:bypass": 0.0 if s["loudness"] else 1.0,
        "f1mozartCompressor:bypass": 0.0 if s["compression"] else 1.0,
        "f4mozartCompressorDualBand:bypass": 0.0 if s["compression"] else 1.0,
    }


# --- salvataggio (file di stato di WirePlumber) ----------------------------------------------------------
def load():
    """Impostazioni salvate (dict completo), oppure None se non ce ne sono."""
    try:
        with open(STATE, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        return None
    raw = {}
    for ln in lines:
        if "=" in ln and not ln.startswith(("[", "#")):
            k, v = ln.split("=", 1)
            raw[k.strip()] = v.strip()
    js = raw.get("manager.settings")
    if js:
        try:
            return sanitize(json.loads(js.replace("\\s", " ")))
        except (ValueError, TypeError):
            pass
    return None


def save(s):
    """Scrive le impostazioni: i parametri del grafo per lo script Lua e la copia leggibile per il manager."""
    s = sanitize(s)
    lines = ["[%s]" % GROUP]
    for k, v in params(s).items():
        lines.append("%s=%s" % (k, repr(float(v))))
    lines.append("manager.settings=%s" % json.dumps(s, sort_keys=True, separators=(",", ":")))
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(tmp, STATE)
    return s


# --- filtro attivo --------------------------------------------------------------------------------------
def _dump():
    if not shutil.which("pw-dump"):
        return []
    try:
        out = subprocess.run(["pw-dump"], capture_output=True, text=True, timeout=10).stdout
        return json.loads(out or "[]")
    except (subprocess.SubprocessError, ValueError):
        return []


def node_info():
    """(id del nodo, {controllo: valore}) del filtro degli altoparlanti, oppure (None, {})."""
    for o in _dump():
        info = o.get("info") or {}
        if not o.get("type", "").endswith("Node") or (info.get("props") or {}).get("node.name") != NODE:
            continue
        vals = {}
        for p in (info.get("params") or {}).get("Props", []):
            ps = p.get("params") or []
            for k, v in zip(ps[0::2], ps[1::2]):
                vals[k] = v
        return o["id"], vals
    return None, {}


def installed():
    return os.path.exists("/usr/share/mbp143-audio/speakers.json")


def has_bankstown(vals=None):
    if vals:
        return "bassex:amt" in vals
    try:
        with open("/usr/share/mbp143-audio/speakers.json", encoding="utf-8") as f:
            return '"bassex"' in f.read()
    except OSError:
        return False


def apply_live(s):
    """Applica s al filtro attivo con pw-cli. Restituisce (ok, messaggio)."""
    nid, vals = node_info()
    if nid is None:
        return False, ("filtro degli altoparlanti non attivo (cuffie collegate, o DSP non installato): "
                       "le impostazioni salvate valgono quando torna")
    p = params(s)
    if not has_bankstown(vals):
        p = {k: v for k, v in p.items() if not k.startswith("bassex:")}
    body = " ".join('"%s" %s' % (k, repr(float(v))) for k, v in p.items())
    try:
        r = subprocess.run(["pw-cli", "s", str(nid), "Props", "{ params = [ %s ] }" % body],
                           capture_output=True, text=True, timeout=10)
    except subprocess.SubprocessError as e:
        return False, "pw-cli: %s" % e
    if r.returncode != 0:
        return False, (r.stderr or r.stdout).strip()[:200]
    return True, "applicato al filtro attivo (nodo %d)" % nid


def db(x):
    return 20 * math.log10(x) if x > 0 else float("-inf")
