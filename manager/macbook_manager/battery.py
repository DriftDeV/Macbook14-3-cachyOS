"""Batteria: cronologia, sessioni a batteria, registratore e report di MacBook Manager. Senza Qt, senza root.

Fonti:
  - UPower (D-Bus di sistema, GetHistory): carica e potenza dall'installazione, sfoltite nel tempo da UPower;
  - sysfs / proprietà UPower: stato attuale, energia, salute, cicli, temperatura;
  - journal: avvii e sospensioni (PM: suspend entry/exit);
  - registratore (`macbook-manager battery-log`, timer utente ogni minuto): una riga al minuto in
    ~/.local/share/macbook-manager/battery/AAAA-MM.csv con i fattori che spiegano i consumi (Radeon, GPU dello schermo,
    luminosità, filtro audio, flussi audio, Touch Bar, carico, temperatura, app che usano più CPU). Conservati 3 mesi.
Report: ogni sessione a batteria (da quando stacchi l'alimentatore a quando lo ricolleghi) diventa un report JSON in
~/.local/share/macbook-manager/battery/reports/, generato dal registratore al ricollegamento (con notifica).

La potenza letta dalla batteria oscilla di 1-3 W: medie e mediane, e i fattori sono indicazioni, non misure separate.
"""
import csv
import glob
import json
import os
import re
import shutil
import statistics as st
import subprocess
import time

BAT = "/sys/class/power_supply/BAT0"
ADP = "/sys/class/power_supply/ADP1"
UP_DEV = "/org/freedesktop/UPower/devices/battery_BAT0"
DATA = os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "macbook-manager", "battery")
REPORTS = os.path.join(DATA, "reports")
CACHE = os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "macbook-manager")
KEEP_MONTHS = 3
MIN_SESSION_MIN = 15  # sessioni più corte: niente report automatico né notifica

# Stati di UPower
CHARGING, DISCHARGING, EMPTY, FULL, PEND_CHARGE, PEND_DISCHARGE = 1, 2, 3, 4, 5, 6
ON_AC = (CHARGING, FULL, PEND_CHARGE)
STATE_TEXT = {CHARGING: "in carica", DISCHARGING: "a batteria", EMPTY: "vuota", FULL: "carica completa",
              PEND_CHARGE: "in attesa di carica", PEND_DISCHARGE: "in attesa"}

FIELDS = ["ts", "pct", "power_w", "status", "ac", "brightness", "radeon_w", "display_gpu", "audio_dsp", "audio_streams",
          "touchbar", "renderer", "load1", "cpu_temp", "bat_temp", "top_apps"]


def _run(argv, timeout=10):
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                              env={**os.environ, "LC_ALL": "C"}).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _read(path, default=None):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return default


def _num(path, scale=1.0, default=None):
    v = _read(path)
    try:
        return int(v) / scale
    except (TypeError, ValueError):
        return default


# --- stato attuale ----------------------------------------------------------------------------------------
def _up_props():
    names = ["EnergyFull", "EnergyFullDesign", "Energy", "EnergyRate", "Percentage", "Capacity", "TimeToEmpty",
             "TimeToFull", "State", "Temperature"]
    out = _run(["busctl", "--system", "get-property", "org.freedesktop.UPower", UP_DEV,
                "org.freedesktop.UPower.Device"] + names)
    vals = {}
    for name, line in zip(names, out.splitlines()):
        parts = line.split()
        try:
            vals[name] = float(parts[1])
        except (IndexError, ValueError):
            pass
    return vals


def now():
    """Stato attuale della batteria (dict)."""
    p = _up_props()
    i, v = _num(BAT + "/current_now", 1e6), _num(BAT + "/voltage_now", 1e6)
    full, design = _num(BAT + "/charge_full", 1e6), _num(BAT + "/charge_full_design", 1e6)
    ac = _read(ADP + "/online") == "1"
    return {
        "pct": _num(BAT + "/capacity") if p.get("Percentage") is None else p["Percentage"],
        "status": _read(BAT + "/status", "?"),
        "ac": ac,
        "power_w": round(i * v, 2) if i is not None and v is not None else p.get("EnergyRate"),
        "energy_wh": p.get("Energy"),
        "full_wh": p.get("EnergyFull"),
        "design_wh": p.get("EnergyFullDesign"),
        "health": round(100 * full / design, 1) if full and design else p.get("Capacity"),
        "cycles": _num(BAT + "/cycle_count"),
        "temp": p.get("Temperature") or _num(BAT + "/temp", 10),
        "time_to_empty": p.get("TimeToEmpty") or 0,
        "time_to_full": p.get("TimeToFull") or 0,
    }


def full_wh():
    return _up_props().get("EnergyFull") or 72.0


# --- cronologia di UPower --------------------------------------------------------------------------------
def upower_history(kind, seconds, resolution=4000):
    """[(t, valore, stato)] in ordine di tempo; kind = charge | rate. Scarta i campioni a 0 dei riavvii."""
    out = _run(["busctl", "--system", "--json=short", "call", "org.freedesktop.UPower", UP_DEV,
                "org.freedesktop.UPower.Device", "GetHistory", "suu", kind, str(int(seconds)), str(resolution)], 20)
    try:
        data = json.loads(out)["data"][0]
    except (ValueError, KeyError, IndexError, TypeError):
        return []
    pts = sorted((int(t), float(v), int(s)) for t, v, s in data)
    if kind == "charge":
        pts = [p for p in pts if p[2] != 0 and p[1] > 0]
    else:
        pts = [p for p in pts if p[2] != 0]
    return pts


# --- eventi dal journal ----------------------------------------------------------------------------------
def events(since):
    """{"boots": [t], "suspends": [(inizio, fine)], "journal_start": t} dal journal, da `since` (epoch) in poi.
    journal_start: primo istante coperto dal journal (prima, sospensioni e riavvii non sono noti)."""
    boots, first = [], None
    out = _run(["journalctl", "--list-boots", "-o", "json", "--no-pager"], 20)
    try:
        for b in json.loads(out or "[]"):
            t = b.get("first_entry", 0) / 1e6
            first = t if first is None else min(first, t)
            if t >= since:
                boots.append(t)
    except ValueError:
        pass
    sus, start = [], None
    out = _run(["journalctl", "-t", "kernel", "-o", "short-unix", "--no-pager", "-q", "--since", "@%d" % int(since),
                "-g", r"PM: suspend (entry|exit)"], 30)
    for line in out.splitlines():
        try:
            t = float(line.split()[0])
        except (IndexError, ValueError):
            continue
        if "suspend entry" in line:
            start = t
        elif "suspend exit" in line and start is not None:
            sus.append((start, t))
            start = None
    return {"boots": boots, "suspends": sus, "journal_start": first or time.time()}


def ac_bands(charge):
    """[(inizio, fine)] dei periodi con l'alimentatore, dalla cronologia di carica."""
    bands, start = [], None
    for t, _v, s in charge:
        if s in ON_AC and start is None:
            start = t
        elif s not in ON_AC and start is not None:
            bands.append((start, t))
            start = None
    if start is not None:
        bands.append((start, int(time.time())))
    return bands


# --- registratore -----------------------------------------------------------------------------------------
def _brightness():
    for d in glob.glob("/sys/class/backlight/*"):
        cur, mx = _num(d + "/brightness"), _num(d + "/max_brightness")
        if cur is not None and mx:
            return round(100 * cur / mx)
    return ""


def _radeon_w():
    for h in glob.glob("/sys/class/hwmon/hwmon*"):
        if _read(h + "/name") == "amdgpu":
            v = _num(h + "/power1_average", 1e6) or _num(h + "/power1_input", 1e6)
            return round(v, 2) if v is not None else ""
    return ""


def _cpu_temp():
    for h in glob.glob("/sys/class/hwmon/hwmon*"):
        if _read(h + "/name") == "coretemp":
            v = _num(h + "/temp1_input", 1000)
            return round(v, 1) if v is not None else ""
    return ""


def _display_gpu():
    for c in glob.glob("/sys/class/drm/card*-eDP-*"):
        if _read(c + "/enabled") == "enabled":
            card = os.path.basename(c).split("-")[0]
            drv = os.path.basename(os.path.realpath("/sys/class/drm/%s/device/driver" % card))
            return {"i915": "intel", "amdgpu": "radeon"}.get(drv, drv)
    return ""


def _audio():
    state = "assente"
    for ln in _run(["pactl", "list", "sinks", "short"], 5).splitlines():
        f = ln.split("\t")
        if len(f) > 4 and f[1] == "audio_effect.mbp143-speakers":
            state = f[4].lower()
    streams = len([ln for ln in _run(["pactl", "list", "sink-inputs", "short"], 5).splitlines() if ln.strip()])
    return state, streams


def _touchbar():
    mode = _read("/run/macbookpro14-3/touchbar/mode", "")
    renderer = next((r for r in ("omabar", "tiny-dfr") if os.path.exists("/run/macbookpro14-3/touchbar/" + r)),
                    "t1bridge" if mode == "display" else "")
    return mode, renderer


def _top_apps(n=3):
    """App che hanno usato più CPU dall'ultimo campione: "nome:% di un core;..." (raggruppate per nome)."""
    tick = os.sysconf("SC_CLK_TCK")
    cur = {}
    for d in glob.glob("/proc/[0-9]*"):
        try:
            with open(d + "/stat") as f:
                s = f.read()
            comm = s[s.index("(") + 1:s.rindex(")")]
            fields = s[s.rindex(")") + 2:].split()
            cur[os.path.basename(d)] = (comm, int(fields[11]) + int(fields[12]))
        except (OSError, ValueError, IndexError):
            continue
    path = os.path.join(CACHE, "procstat.json")
    t = time.time()
    try:
        with open(path) as f:
            prev = json.load(f)
    except (OSError, ValueError):
        prev = {}
    os.makedirs(CACHE, exist_ok=True)
    with open(path, "w") as f:
        json.dump({"t": t, "p": cur}, f)
    dt = t - prev.get("t", t)
    if dt <= 0 or dt > 600:
        return ""
    agg = {}
    old = prev.get("p", {})
    for pid, (comm, ticks) in cur.items():
        if pid in old and old[pid][0] == comm:
            d = ticks - old[pid][1]
            if d > 0:
                agg[comm] = agg.get(comm, 0) + d / tick / dt * 100
    top = sorted(agg.items(), key=lambda x: -x[1])[:n]
    return ";".join("%s:%.0f" % (c.replace(";", "_").replace(":", "_"), v) for c, v in top if v >= 1)


def sample():
    """Un campione del registratore (dict con i campi FIELDS)."""
    b = now()
    audio, streams = _audio()
    mode, renderer = _touchbar()
    return {
        "ts": int(time.time()), "pct": round(b["pct"], 1) if b["pct"] is not None else "",
        "power_w": round(b["power_w"], 2) if b["power_w"] is not None else "", "status": b["status"],
        "ac": int(b["ac"]), "brightness": _brightness(), "radeon_w": _radeon_w(), "display_gpu": _display_gpu(),
        "audio_dsp": audio, "audio_streams": streams, "touchbar": mode, "renderer": renderer,
        "load1": round(os.getloadavg()[0], 2), "cpu_temp": _cpu_temp(),
        "bat_temp": b["temp"] if b["temp"] is not None else "", "top_apps": _top_apps(),
    }


def _csv_path(t):
    return os.path.join(DATA, time.strftime("%Y-%m", time.localtime(t)) + ".csv")


def log_sample():
    """Usato dal timer: scrive un campione, sfoltisce i mesi vecchi, genera il report al ricollegamento."""
    s = sample()
    path = _csv_path(s["ts"])
    os.makedirs(DATA, exist_ok=True)
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow(s)
    for old in sorted(glob.glob(os.path.join(DATA, "????-??.csv")))[:-KEEP_MONTHS]:
        os.remove(old)
    # transizione batteria -> alimentatore: report della sessione appena chiusa
    state_path = os.path.join(CACHE, "battery-state.json")
    try:
        with open(state_path) as f:
            last = json.load(f)
    except (OSError, ValueError):
        last = {}
    with open(state_path, "w") as f:
        json.dump({"ac": s["ac"], "ts": s["ts"]}, f)
    report = None
    if last.get("ac") == 0 and s["ac"] == 1:
        report = auto_report()
    return s, report


def load_samples(since, until=None):
    """Campioni del registratore fra since e until (lista di dict con numeri dove possibile)."""
    until = until or time.time()
    out = []
    for path in sorted(glob.glob(os.path.join(DATA, "????-??.csv"))):
        try:
            with open(path, newline="") as f:
                for row in csv.DictReader(f):
                    try:
                        t = int(row["ts"])
                    except (KeyError, ValueError, TypeError):
                        continue
                    if since <= t <= until:
                        for k in ("pct", "power_w", "brightness", "radeon_w", "load1", "cpu_temp", "bat_temp"):
                            try:
                                row[k] = float(row[k])
                            except (KeyError, ValueError, TypeError):
                                row[k] = None
                        row["ts"], row["ac"] = t, row.get("ac") == "1"
                        try:
                            row["audio_streams"] = int(row.get("audio_streams") or 0)
                        except ValueError:
                            row["audio_streams"] = 0
                        out.append(row)
        except OSError:
            continue
    return out


def logger_state():
    """(attivo, ultimo campione epoch o None, campioni totali)."""
    active = _run(["systemctl", "--user", "is-active", "macbook-manager-battery-log.timer"], 5).strip() == "active"
    last, total = None, 0
    for path in sorted(glob.glob(os.path.join(DATA, "????-??.csv"))):
        try:
            with open(path) as f:
                lines = f.read().splitlines()[1:]
        except OSError:
            continue
        total += len(lines)
        if lines:
            try:
                last = int(lines[-1].split(",")[0])
            except ValueError:
                pass
    return active, last, total


# --- sessioni e report -----------------------------------------------------------------------------------
def sessions(charge, rate, ev):
    """Sessioni a batteria dalla cronologia: dict con inizio/fine, carica, sospensioni, potenza attiva."""
    out, cur = [], None
    for t, v, s in charge:
        if s in ON_AC:
            if cur:
                cur["end"], cur["end_pct"], cur["closed"] = t, cur["last_pct"], True
                out.append(cur)
                cur = None
        elif s in (DISCHARGING, PEND_DISCHARGE, EMPTY):
            if cur is None:
                cur = {"start": t, "start_pct": v, "closed": False}
            cur["last_pct"], cur["last_t"] = v, t
    if cur:
        cur["end"], cur["end_pct"] = cur["last_t"], cur["last_pct"]
        out.append(cur)
    res = []
    js = ev.get("journal_start", 0)
    for c in out:
        a, b = c["start"], c["end"]
        sus = [(max(x, a), min(y, b)) for x, y in ev["suspends"] if y > a and x < b]
        # Prima dell'inizio del journal: pause stimate dai buchi della cronologia (sospeso o spento).
        gaps = []
        if a < js:
            seg = [t for t, _v, _s in charge if a <= t <= min(b, js)]
            gaps = [(x, y) for x, y in zip(seg, seg[1:]) if y - x > 600]
            sus = sorted(sus + gaps)
        sus_s = sum(y - x for x, y in sus)
        sus_drop = 0.0
        for x, y in sus:
            p0 = _value_at(charge, x)
            p1 = _value_at(charge, y)
            if p0 is not None and p1 is not None:
                sus_drop += max(0.0, p0 - p1)
        in_sus = lambda t, sus=sus: any(x - 30 <= t <= y + 30 for x, y in sus)  # noqa: E731
        watts = [v for t, v, s in rate if a <= t <= b and s in (DISCHARGING, PEND_DISCHARGE) and v > 0.5
                 and not in_sus(t)]
        c.update(suspends=sus, suspend_s=sus_s, suspend_drop=sus_drop, watts=watts, estimated=bool(gaps),
                 journal=a >= js,
                 boots=[t for t in ev["boots"] if a < t < b], duration_s=b - a)
        res.append(c)
    return res


def _value_at(series, t):
    best = None
    for x, v, _s in series:
        if x <= t:
            best = v
        else:
            return best if best is not None else v
    return best


def summarize(sess, samples=None, full=None):
    """Report (dict) di una sessione, con i fattori del registratore se ci sono campioni."""
    full = full or full_wh()
    dur_h = sess["duration_s"] / 3600
    active_h = max(dur_h - sess["suspend_s"] / 3600, 1e-6)
    drop = sess["start_pct"] - sess["end_pct"]
    active_drop = max(drop - sess["suspend_drop"], 0.0)
    w = sess["watts"]
    energy = drop / 100 * full
    avg_from_energy = active_drop / 100 * full / active_h if active_h > 0.05 else None
    avg_w = round(st.mean(w), 1) if w else (round(avg_from_energy, 1) if avg_from_energy else None)
    rep = {
        "start": sess["start"], "end": sess["end"], "closed": sess["closed"],
        "start_pct": round(sess["start_pct"], 1), "end_pct": round(sess["end_pct"], 1), "drop_pct": round(drop, 1),
        "duration_min": round(dur_h * 60), "active_min": round(active_h * 60),
        "suspend_min": round(sess["suspend_s"] / 60), "suspend_count": len(sess["suspends"]),
        "suspend_drop_pct": round(sess["suspend_drop"], 1),
        "suspend_w": round(sess["suspend_drop"] / 100 * full / (sess["suspend_s"] / 3600), 2)
        if sess["suspend_s"] > 600 else None,
        "boots": len(sess["boots"]), "estimated_pauses": sess.get("estimated", False),
        "journal": sess.get("journal", True),
        "energy_wh": round(energy, 1), "full_wh": round(full, 1),
        "avg_w": avg_w, "median_w": round(st.median(w), 1) if w else None,
        "p90_w": round(sorted(w)[int(len(w) * 0.9) - 1], 1) if len(w) >= 10 else None,
        "min_w": round(min(w), 1) if w else None, "max_w": round(max(w), 1) if w else None,
        "pct_per_h": round(active_drop / active_h, 1) if active_h > 0.05 else None,
        "projected_h": round(full / avg_w, 1) if avg_w else None,
        "factors": factors(samples) if samples else None,
    }
    return rep


def factors(samples):
    """Fattori dei consumi dai campioni del registratore (solo quelli a batteria)."""
    bat = [s for s in samples if not s["ac"]]
    if len(bat) < 3:
        return None

    def avg(key):
        v = [s[key] for s in bat if s.get(key) is not None]
        return round(st.mean(v), 1) if v else None

    def share(pred):
        return round(100 * sum(1 for s in bat if pred(s)) / len(bat))

    apps = {}
    for s in bat:
        for item in (s.get("top_apps") or "").split(";"):
            if ":" in item:
                name, pct = item.rsplit(":", 1)
                try:
                    apps[name] = apps.get(name, 0) + float(pct) / 100  # minuti di un core (campioni al minuto)
                except ValueError:
                    pass
    gpus = {}
    for s in bat:
        g = s.get("display_gpu") or "?"
        gpus[g] = gpus.get(g, 0) + 1
    return {
        "samples": len(bat),
        "radeon_w": avg("radeon_w"), "brightness": avg("brightness"), "load1": avg("load1"),
        "cpu_temp": avg("cpu_temp"), "bat_temp": avg("bat_temp"),
        "display_gpu": max(gpus, key=gpus.get),
        "audio_running_pct": share(lambda s: s.get("audio_dsp") == "running"),
        "audio_streams_pct": share(lambda s: s.get("audio_streams", 0) > 0),
        "touchbar_display_pct": share(lambda s: s.get("touchbar") == "display"),
        "renderer": max(((s.get("renderer") or "") for s in bat), key=lambda r: sum(1 for s in bat if s.get("renderer") == r)),
        "top_apps": [(n, round(m, 1)) for n, m in sorted(apps.items(), key=lambda x: -x[1])[:6]],
    }


def all_reports(days=60):
    """Report di tutte le sessioni nella cronologia di UPower (le più recenti prima)."""
    span = days * 86400
    charge, rate = upower_history("charge", span), upower_history("rate", span)
    if not charge:
        return []
    ev = events(charge[0][0])
    full = full_wh()
    reps = []
    for s in sessions(charge, rate, ev):
        if s["duration_s"] < 120:
            continue
        reps.append(summarize(s, load_samples(s["start"], s["end"]), full))
    saved = {r["start"]: r for r in saved_reports()}
    for r in reps:  # i report salvati dal registratore restano la fonte per le sessioni chiuse
        if r["start"] in saved and saved[r["start"]].get("factors") and not r.get("factors"):
            r["factors"] = saved[r["start"]]["factors"]
    return sorted(reps, key=lambda r: -r["start"])


def saved_reports():
    out = []
    for p in sorted(glob.glob(os.path.join(REPORTS, "*.json"))):
        try:
            with open(p) as f:
                out.append(json.load(f))
        except (OSError, ValueError):
            continue
    return out


def auto_report():
    """Report della sessione appena chiusa: salvato e notificato (chiamato dal registratore)."""
    reps = [r for r in all_reports(days=3) if r["closed"]]
    if not reps:
        return None
    r = reps[0]
    if r["duration_min"] < MIN_SESSION_MIN or time.time() - r["end"] > 900:
        return None
    os.makedirs(REPORTS, exist_ok=True)
    path = os.path.join(REPORTS, time.strftime("%Y%m%d-%H%M.json", time.localtime(r["start"])))
    with open(path, "w") as f:
        json.dump(r, f, indent=1)
    if shutil.which("notify-send"):
        _run(["notify-send", "-a", "MacBook Manager", "-i", "battery", "Sessione a batteria: %s" % hm(r["duration_min"]),
              short_text(r)], 5)
    return r


# --- testo ------------------------------------------------------------------------------------------------
def hm(minutes):
    if minutes is None:
        return "-"
    minutes = int(round(minutes))
    return "%d h %02d min" % (minutes // 60, minutes % 60) if minutes >= 60 else "%d min" % minutes


def short_text(r):
    parts = ["%.0f → %.0f %%" % (r["start_pct"], r["end_pct"])]
    if r["avg_w"]:
        parts.append("%.1f W in media" % r["avg_w"])
    if r["projected_h"]:
        parts.append("~%s con la batteria piena" % hm(r["projected_h"] * 60))
    return ", ".join(parts)


def _clock(t):
    return time.strftime("%d/%m %H:%M", time.localtime(t))


def report_lines(r, previous=None):
    """Report leggibile (lista di righe) di una sessione; previous = report delle sessioni precedenti."""
    L = ["Sessione a batteria %s → %s%s" % (_clock(r["start"]), _clock(r["end"]),
                                           "" if r["closed"] else " (in corso)"),
         "  durata %s, di cui attiva %s; carica %.0f → %.0f %% (-%.0f punti, ~%.1f Wh su %.0f)" % (
             hm(r["duration_min"]), hm(r["active_min"]), r["start_pct"], r["end_pct"], r["drop_pct"], r["energy_wh"],
             r["full_wh"])]
    if r["avg_w"]:
        L.append("  potenza in uso: media %.1f W, mediana %s W, 90%% dei campioni sotto %s W (min %s, max %s)" % (
            r["avg_w"], r["median_w"], r["p90_w"] or "-", r["min_w"], r["max_w"]))
        L.append("  ritmo %s %%/h → autonomia stimata con la batteria piena: %s" % (
            r["pct_per_h"] if r["pct_per_h"] is not None else "-", hm(r["projected_h"] * 60) if r["projected_h"] else "-"))
    if r["suspend_count"]:
        L.append("  %s: %d per %s, %s%s" % (
            "pause (sospeso o spento, stimate: journal non disponibile)" if r.get("estimated_pauses") else "sospensioni",
            r["suspend_count"], hm(r["suspend_min"]),
            "-%.1f punti" % r["suspend_drop_pct"] if r["suspend_drop_pct"] >= 0.1 else "consumo trascurabile",
            " (~%.2f W)" % r["suspend_w"] if r["suspend_w"] and r["suspend_drop_pct"] >= 0.1 else ""))
    elif not r.get("journal", True):
        L.append("  sospensioni e riavvii: sconosciuti (journal non disponibile per questo periodo)")
    if r["boots"]:
        L.append("  riavvii durante la sessione: %d" % r["boots"])
    f = r.get("factors")
    if f:
        L.append("  fattori (registratore, %d campioni):" % f["samples"])
        bits = []
        if f["radeon_w"] is not None:
            bits.append("Radeon %.1f W in media" % f["radeon_w"])
        if f["display_gpu"]:
            bits.append("schermo sulla %s" % {"intel": "Intel", "radeon": "Radeon"}.get(f["display_gpu"], f["display_gpu"]))
        if f["brightness"] is not None:
            bits.append("luminosità %.0f %%" % f["brightness"])
        L.append("    " + ", ".join(bits))
        L.append("    filtro audio al lavoro %d %% del tempo, flussi audio aperti %d %%; Touch Bar in display %d %%%s" % (
            f["audio_running_pct"], f["audio_streams_pct"], f["touchbar_display_pct"],
            " (%s)" % f["renderer"] if f["renderer"] else ""))
        if f["load1"] is not None:
            L.append("    carico medio %.1f, CPU %s °C, batteria %s °C" % (f["load1"], f["cpu_temp"], f["bat_temp"]))
        if f["top_apps"]:
            L.append("    app che hanno usato più CPU (minuti di un core): " +
                     ", ".join("%s %.0f" % (n, m) for n, m in f["top_apps"]))
    else:
        L.append("  fattori: nessun campione del registratore in questa sessione")
    if previous:
        ws = [p["avg_w"] for p in previous if p.get("avg_w")]
        if ws and r["avg_w"]:
            m = st.mean(ws)
            diff = r["avg_w"] - m
            L.append("  rispetto alle %d sessioni precedenti (%.1f W in media): %s%.1f W" % (
                len(ws), m, "+" if diff >= 0 else "", diff))
    return L


def html_report(r, previous=None, charge=None, rate=None):
    """Report HTML autonomo (grafico SVG incluso) di una sessione."""
    import html
    lines = report_lines(r, previous)
    svg = _svg_chart(charge or [], rate or [], r["start"], r["end"]) if charge else ""
    body = "".join("<p>%s</p>" % html.escape(ln.strip()) for ln in lines[1:])
    return ("<!doctype html><meta charset='utf-8'><title>Report batteria</title>"
            "<style>body{font-family:sans-serif;max-width:820px;margin:2rem auto;color:#222}"
            "p{margin:.3rem 0}h1{font-size:20px}</style>"
            "<h1>%s</h1>%s%s<p style='color:#888;font-size:12px'>MacBook Manager, MacBookPro14,3</p>"
            % (html.escape(lines[0]), svg, body))


def _svg_chart(charge, rate, a, b, w=800, h=260):
    pts_c = [(t, v) for t, v, _s in charge if a - 60 <= t <= b + 60]
    pts_r = [(t, v) for t, v, s in rate if a <= t <= b and v > 0.5]
    if len(pts_c) < 2:
        return ""
    span = max(b - a, 1)
    X = lambda t: 40 + (t - a) / span * (w - 50)  # noqa: E731
    Yc = lambda v: 10 + (100 - v) / 100 * (h * 0.55)  # noqa: E731
    top_r = max(35, max((v for _t, v in pts_r), default=0))
    Yr = lambda v: h * 0.62 + (top_r - v) / top_r * (h * 0.33)  # noqa: E731
    pc = " ".join("%.1f,%.1f" % (X(t), Yc(v)) for t, v in pts_c)
    pr = " ".join("%.1f,%.1f" % (X(t), Yr(v)) for t, v in pts_r)
    ticks = "".join("<text x='%.0f' y='%d' font-size='11' fill='#888'>%s</text>" % (
        X(t), h - 2, time.strftime("%H:%M", time.localtime(t))) for t in range(int(a), int(b) + 1, max(span // 6, 60)))
    return ("<svg viewBox='0 0 %d %d' width='100%%'><polyline points='%s' fill='none' stroke='#2a78d6' stroke-width='2'/>"
            "<polyline points='%s' fill='none' stroke='#eb6834' stroke-width='1.5'/>"
            "<text x='2' y='14' font-size='11' fill='#2a78d6'>carica %%</text>"
            "<text x='2' y='%d' font-size='11' fill='#eb6834'>W</text>%s</svg>" % (w, h, pc, pr, int(h * 0.62), ticks))


# --- statistiche rapide per la GUI --------------------------------------------------------------------------
def recent_power(rate, minutes=60):
    t0 = time.time() - minutes * 60
    w = [v for t, v, s in rate if t >= t0 and s in (DISCHARGING, PEND_DISCHARGE) and v > 0.5]
    return round(st.mean(w), 1) if w else None


def parse_top(top):
    return [(n, float(p)) for n, p in (x.rsplit(":", 1) for x in (top or "").split(";") if ":" in x)
            if re.match(r"^[\d.]+$", p)]
