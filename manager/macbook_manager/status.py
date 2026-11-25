"""Lettura dello stato, senza root: /sys, /run, journal, dkms, iw, systemctl.

Ogni voce è un dict: group, id, label, value, level (ok|warn|err|info), hint, fix (id di un'azione o None).
"""
import glob
import os
import re
import subprocess
import time

from . import CONFDIR, LIBDIR

OK, WARN, ERR, INFO = "ok", "warn", "err", "info"
_cache = {}


def _read(path, default=None):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return default


def _int(path, default=None):
    v = _read(path)
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _run(argv, timeout=5):
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                              env={**os.environ, "LC_ALL": "C"}).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _cached(key, ttl, fn):
    now = time.monotonic()
    hit = _cache.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    val = fn()
    _cache[key] = (now, val)
    return val


def invalidate():
    _cache.clear()


def read_conf(name):
    """KEY=VALUE da /etc/macbookpro14-3/<name>.conf (senza eseguirlo)."""
    out = {}
    for line in (_read(os.path.join(CONFDIR, name + ".conf"), "") or "").splitlines():
        m = re.match(r"^\s*([A-Z_][A-Z0-9_]*)=(.*)$", line)
        if m:
            out[m.group(1)] = m.group(2).strip().strip('"')
    return out


def _hwmon(name):
    for h in glob.glob("/sys/class/hwmon/hwmon*"):
        if _read(h + "/name") == name:
            return h
    return None


def _item(group, id_, label, value, level=INFO, hint="", fix=None):
    return {"group": group, "id": id_, "label": label, "value": value, "level": level, "hint": hint, "fix": fix}


def user_unit_active(unit):
    return _run(["systemctl", "--user", "is-active", unit]).strip() == "active"


def system_unit_active(unit):
    return _run(["systemctl", "is-active", unit]).strip() == "active"


# --- driver ------------------------------------------------------------------------------------------

DRIVERS = [  # (modulo DKMS, etichetta, serve solo in modalità display)
    ("appleibridge", "Driver Touch Bar (modalità tastiera)", False),
    ("snd_hda_macbookpro", "Driver audio CS8409", False),
    ("t1bridge-appletbdrm", "Driver Touch Bar (modalità display)", True),
    ("t1bridge-uvc", "Driver webcam H.264 (modalità display)", True),
]


def dkms_status():
    """{modulo: {kernel: stato}} da `dkms status`."""
    out = {}
    for line in _run(["dkms", "status"], timeout=20).splitlines():
        m = re.match(r"^([^/]+)/([^,]+), ([^,]+), [^:]+: (.*)$", line)
        if m:
            out.setdefault(m.group(1), {})[m.group(3)] = m.group(4)
    return out


def drivers():
    kernel = os.uname().release
    st = _cached("dkms", 30, dkms_status)
    display = read_conf("touchbar").get("TOUCHBAR_MODE") == "display"
    items = []
    for mod, label, display_only in DRIVERS:
        if mod not in st:
            continue
        state = st[mod].get(kernel, "")
        if state.startswith("installed"):
            items.append(_item("Driver", mod, label, "pronto per " + kernel, OK))
        else:
            lvl = WARN if (display_only and not display) else ERR
            items.append(_item("Driver", mod, label, "non compilato per " + kernel, lvl,
                               "Dopo un aggiornamento del kernel: ricompila i driver (DKMS).", "dkms-build"))
    if not items:
        items.append(_item("Driver", "dkms", "Driver DKMS", "nessuno installato", WARN,
                           "Lancia install.sh dalla repo."))
    return items


# --- Touch Bar ---------------------------------------------------------------------------------------

def touchbar_mode():
    return _read("/run/macbookpro14-3/touchbar/mode", "keyboard")


TDFR_UNIT = "macbookpro14-3-tiny-dfr.service"
TDFR_BIN = "/usr/local/lib/macbookpro14-3/tiny-dfr/tiny-dfr"


def touchbar_renderer():
    """Renderer in uso in modalità display: "tiny-dfr" (scripts/install-tiny-dfr.sh) o "t1bridge" (fnstrip o quello
    di T1Bridge). touchbar-mode crea il file quando avvia tiny-dfr."""
    return "tiny-dfr" if os.path.exists("/run/macbookpro14-3/touchbar/tiny-dfr") else "t1bridge"


def touchbar():
    if not os.path.exists("/usr/local/bin/touchbar-mode"):
        return [_item("Touch Bar", "touchbar", "Modalità", "touchbar-mode non installato", INFO,
                      "Modalità display: scripts/install-touchbar-display.sh")]
    saved = read_conf("touchbar").get("TOUCHBAR_MODE", "keyboard")
    cur = touchbar_mode()
    names = {"display": "display (grafica)", "keyboard": "tastiera (layout fissi)"}
    items = []
    dark = cur == "keyboard" and os.path.exists("/run/macbookpro14-3/touchbar/display-this-boot")
    if dark:
        items.append(_item("Touch Bar", "touchbar", "Modalità", "tastiera, barra spenta (tocco attivo)", WARN,
                           "Dopo la modalità display il T1 si azzera solo con uno spegnimento completo (~30 s).",
                           "poweroff"))
    elif saved == cur:
        items.append(_item("Touch Bar", "touchbar", "Modalità", names.get(cur, cur), OK))
    elif saved == "keyboard" and cur == "display":
        items.append(_item("Touch Bar", "touchbar", "Modalità", "display, tastiera dal prossimo spegnimento", INFO,
                           "Il T1 riparte in modalità tastiera solo dopo uno spegnimento completo (~30 s).",
                           "poweroff"))
    else:
        items.append(_item("Touch Bar", "touchbar", "Modalità", "%s, salvata: %s" % (cur, saved), WARN,
                           "La modalità salvata non è attiva.", "touchbar-" + saved))
    if cur == "display" and touchbar_renderer() == "tiny-dfr":
        r = system_unit_active(TDFR_UNIT)
        items.append(_item("Touch Bar", "renderer", "Renderer", "tiny-dfr, " + ("attivo" if r else "fermo"),
                           OK if r else ERR, "" if r else "Barra senza grafica: riavvia tiny-dfr "
                           "(journalctl -u %s)." % TDFR_UNIT, None if r else "renderer-tiny-dfr"))
    elif cur == "display":
        r = user_unit_active("macbookpro14-3-touchbar-renderer.service")
        items.append(_item("Touch Bar", "renderer", "Renderer", "attivo" if r else "fermo", OK if r else ERR,
                           "" if r else "Barra senza grafica: riavvia il renderer.", None if r else "renderer-restart"))
    if cur == "display":
        w = user_unit_active("macbookpro14-3-webcam.service")
        items.append(_item("Touch Bar", "webcam", "Webcam virtuale (Discord)", "accesa" if w else "spenta", INFO,
                           "Accesa: il LED della camera resta acceso."))
    return items


# --- sospensione -------------------------------------------------------------------------------------

def sleep_mode():
    out = _cached("sleepconf", 10, lambda: _run(["systemd-analyze", "cat-config", "systemd/sleep.conf"]))
    modes = re.findall(r"^MemorySleepMode=(\S+)", out, re.M)
    return modes[-1] if modes else "default"


def sleep_history(boot="0"):
    """Cicli di sospensione dal journal (come scripts/sleep-test.sh report)."""
    out = _run(["journalctl", "-b", boot, "-o", "short-unix", "--no-pager", "-q",
                "-t", "systemd-sleep", "-t", "systemd-logind", "-t", "kernel", "-t", "macbookpro14-3-sleep"], timeout=20)
    cyc, cur, lid, opened, pre = [], None, "?", 0.0, None
    for line in out.splitlines():
        try:
            t = float(line.split()[0])
        except (IndexError, ValueError):
            continue
        if "Lid closed" in line:
            lid = "chiuso"
        elif "Lid opened" in line:
            lid, opened = "aperto", t
            if cur and cur.get("end") and t - cur["end"] <= 5:
                cur["cause"] = "coperchio aperto"
        elif "Performing sleep operation" in line:
            cur = {"start": t, "lid": lid, "mode": "?"}
            if pre:  # l'hook "pre" scrive la batteria prima di questa riga
                cur["b0"], pre = pre, None
            cyc.append(cur)
        elif cur and "PM: suspend entry" in line:
            m = re.search(r"\((\w+)\)", line)
            cur["mode"] = m.group(1) if m else "?"
        elif "pre suspend: fatto" in line:
            m = re.search(r"(\d+)% (\d+) mAh ac=(\d)", line)
            pre = m.groups() if m else None
        elif cur and "returned from sleep" in line:
            cur["end"] = t
            if t - opened <= 5:
                cur["cause"] = "coperchio aperto"
        elif cur and "post suspend: batteria" in line:
            m = re.search(r"(\d+)% (\d+) mAh", line)
            if m:
                cur["b1"] = m.groups()
    for c in cyc:
        c["spontaneous"] = c["lid"] == "chiuso" and "end" in c and not c.get("cause")
        if "end" in c and not c.get("cause"):
            c["cause"] = "SENZA aprire il coperchio" if c["spontaneous"] else "tasto, sveglia o altro"
        c["minutes"] = (c["end"] - c["start"]) / 60 if "end" in c else None
        c["mah"] = int(c["b0"][1]) - int(c["b1"][1]) if "b0" in c and "b1" in c else None
    return cyc


def sleep():
    mode = sleep_mode()
    items = []
    if mode == "deep":
        items.append(_item("Sospensione", "sleepmode", "Modalità", "S3 (deep): ventole ferme", OK))
    else:
        items.append(_item("Sospensione", "sleepmode", "Modalità", mode, WARN,
                           "s2idle su questo Mac non è un vero sonno: ventole accese e risvegli a coperchio chiuso.",
                           "sleep-deep"))
    hist = _cached("sleephist", 60, sleep_history)
    spont = sum(1 for c in hist if c["spontaneous"])
    deep_spont = sum(1 for c in hist if c["spontaneous"] and c["mode"] == "deep")
    val = "%d sospensioni in questo avvio" % len(hist)
    if spont:
        val += ", %d risvegli a coperchio chiuso" % spont
    items.append(_item("Sospensione", "sleephist", "Storico", val, WARN if deep_spont else INFO,
                       "Dettagli nella scheda Sospensioni."))
    return items


# --- rete --------------------------------------------------------------------------------------------

def wifi():
    ifs = [os.path.basename(os.path.dirname(p)) for p in glob.glob("/sys/class/net/*/wireless")]
    if not ifs:
        return [_item("Rete", "wifi", "Wi-Fi", "nessuna scheda (driver scaricato?)", ERR,
                      "Ricarica il driver Wi-Fi.", "wifi-reload")]
    dev = ifs[0]
    link = _run(["iw", "dev", dev, "link"])
    if "Connected" not in link:
        return [_item("Rete", "wifi", "Wi-Fi", "non connesso", WARN, "Se le reti non compaiono: ricarica il driver.",
                      "wifi-reload")]
    g = lambda k: (re.search(r"^\s*" + k + r":\s*(.+)$", link, re.M) or [None, "?"])[1]
    freq = float(g("freq") or 0) if g("freq") != "?" else 0
    width = re.search(r"width: (\d+ MHz)", _run(["iw", "dev", dev, "info"]))
    band = "5 GHz" if freq > 4900 else "2,4 GHz"
    val = "%s, %s%s, %s, ↓%s" % (g("SSID"), band, ", " + width.group(1) if width else "", g("signal"),
                                 g("rx bitrate").split(" MBit")[0] + " Mbit/s")
    return [_item("Rete", "wifi", "Wi-Fi", val, OK if freq > 4900 else WARN,
                  "" if freq > 4900 else "Su 2,4 GHz la velocità è molto più bassa.")]


# --- energia e temperature ---------------------------------------------------------------------------

def battery():
    b = "/sys/class/power_supply/BAT0"
    if not os.path.isdir(b):
        return []
    cap, status = _int(b + "/capacity", 0), _read(b + "/status", "?")
    cur, volt = _int(b + "/current_now", 0), _int(b + "/voltage_now", 0)
    now, full, design = _int(b + "/charge_now", 0), _int(b + "/charge_full", 0), _int(b + "/charge_full_design", 0)
    watts = cur * volt / 1e12
    names = {"Discharging": "a batteria", "Charging": "in carica", "Full": "carica", "Not charging": "collegato"}
    val = "%d%%, %s" % (cap, names.get(status, status))
    if status == "Discharging" and cur > 0:
        h = now / cur
        val += ", %.1f W, ~%d h %02d min" % (watts, int(h), int(h * 60) % 60)
    elif status == "Charging":
        val += ", %.1f W" % watts
    items = [_item("Energia", "battery", "Batteria", val, WARN if cap < 20 and status == "Discharging" else OK)]
    if design:
        health = 100 * full / design
        items.append(_item("Energia", "health", "Salute batteria", "%.0f%%, %s cicli" % (health, _read(b + "/cycle_count", "?")),
                           OK if health >= 80 else WARN, "" if health >= 80 else "Capacità sotto l'80% dell'originale."))
    return items


def energy():
    items = []
    h = _hwmon("amdgpu")
    if h:
        w = _int(h + "/power1_input") or _int(h + "/power1_average")
        t = _int(h + "/temp1_input")
        dev = os.path.realpath(h + "/device")
        level = _read(dev + "/power_dpm_force_performance_level", "?")
        prof = re.search(r"^\s*\d+\s+(\w+)\s*\*", _read(dev + "/pp_power_profile_mode", "") or "", re.M)
        val = "%s%s, %s" % ("%.1f W, " % (w / 1e6) if w else "", "%d °C" % (t // 1000) if t else "?",
                            "risparmio" if prof and prof.group(1) == "POWER_SAVING" else level)
        items.append(_item("Energia", "radeon", "Radeon", val, INFO,
                           "Schermo e desktop sono sempre sulla Radeon (7-9 W a riposo)."))
    conf = read_conf("power")
    if conf:
        from . import power as P
        parts = []
        for key, _t, label, _e, options, _d, _s in P.SETTINGS:
            v = P.current("BATTERY", key)
            if v != P.current("AC", key) or key == "RADEON_MODE":
                parts.append("%s %s" % (label.lower(), dict(options).get(v, v)))
        items.append(_item("Energia", "powerconf", "Regole a batteria", " · ".join(parts) or "come con l'alimentatore",
                           INFO, "Schede CPU e GPU (/etc/macbookpro14-3/power.conf)"))
    # Stato attuale del turbo (le regole sopra valgono solo a batteria).
    nt_now = _int("/sys/devices/system/cpu/intel_pstate/no_turbo")
    if nt_now is not None:
        ac = (_int("/sys/class/power_supply/ADP1/online") or 0) == 1
        mx = _int("/sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq")
        ghz = " (massimo %.1f GHz)" % (mx / 1e6) if mx else ""
        if nt_now == 0:
            items.append(_item("Energia", "turbo", "Turbo CPU", "attivo ora" + ghz, OK))
        elif ac:
            items.append(_item("Energia", "turbo", "Turbo CPU", "spento ora, con l'alimentatore collegato" + ghz, WARN,
                               "Doveva riaccendersi collegando l'alimentatore: "
                               "sudo /usr/local/lib/macbookpro14-3/power-source.sh"))
        else:
            items.append(_item("Energia", "turbo", "Turbo CPU", "spento ora (a batteria, come da regola)" + ghz, INFO))
    ct, sm = _hwmon("coretemp"), _hwmon("applesmc")
    parts, lvl = [], OK
    if ct:
        t = _int(ct + "/temp1_input")
        if t:
            parts.append("CPU %d °C" % (t // 1000))
            lvl = ERR if t >= 95000 else WARN if t >= 85000 else OK
    if sm:
        fans = [_int(f) for f in sorted(glob.glob(sm + "/fan[0-9]_input"))]
        parts.append("ventole " + " / ".join("%d" % f for f in fans if f is not None) + " giri/min")
    if parts:
        items.append(_item("Energia", "thermal", "Temperature", ", ".join(parts), lvl))
    return items


# --- Touch ID (scripts/install-touchid.sh) ----------------------------------------------------------

TOUCHID_PAM = "/usr/local/bin/touchid-pam"
PAM_MARKS = ("# macbookpro14-3 touchid-pam", "scripts/install-touchid.sh")
RELAY_LIMIT = 68  # blocco osservato da due tester (T1Bridge issue #14), si recupera solo con lo spegnimento completo


def touchid_lockscreen_on():
    return not any(m in (_read("/etc/pam.d/kde-fingerprint", "") or "") for m in PAM_MARKS)


def touchid_sudo_on():
    return PAM_MARKS[0] in (_read("/etc/pam.d/sudo", "") or "")


def relay_activations():
    out = _run(["journalctl", "-b", "--no-pager", "-q", "-u", "t1bridge-keybag.service"], timeout=10)
    return out.count("Started T1Bridge existing-keybag")


def touchid():
    if not os.path.exists(TOUCHID_PAM):
        return []
    items = []
    if touchbar_mode() != "display":
        items.append(_item("Touch ID", "touchid", "Servizi", "fermi (serve la modalità display)", INFO,
                           "Touch ID usa la configurazione USB 2 del T1."))
    else:
        xart = system_unit_active("t1-xart-storage@t1ncm.service")
        relay = system_unit_active("t1bridge-keybag.service")
        val = "xART %s, relay %s" % ("attivo" if xart else "fermo", "attivo" if relay else "fermo")
        lvl = OK if xart and relay else (WARN if xart else ERR)
        items.append(_item("Touch ID", "touchid", "Servizi", val, lvl,
                           "" if xart else "xART fermo: il passaggio in modalità display lo riavvia (touchbar-mode)."))
    n = _cached("relay", 60, relay_activations)
    lvl = ERR if n >= RELAY_LIMIT - 3 else WARN if n >= 50 else INFO
    items.append(_item("Touch ID", "relaycount", "Attivazioni del relay", "%d in questo avvio (blocco a ~%d)" % (n, RELAY_LIMIT),
                       lvl, "" if lvl == INFO else "Vicino al limite della issue #14: se l'impronta smette di funzionare "
                       "serve uno spegnimento completo. La password resta valida."))
    if os.path.exists("/usr/lib/pam.d/kde-fingerprint"):
        items.append(_item("Touch ID", "tid-lock", "Schermata di blocco", "impronta attiva" if touchid_lockscreen_on()
                           else "solo password", INFO, "Ogni sblocco con l'impronta consuma un'attivazione del relay."))
    else:
        items.append(_item("Touch ID", "tid-lock", "Schermata di blocco", "regolata da hyprlock (auth:fingerprint)", INFO,
                           "Su Hyprland/Omarchy l'impronta del blocco schermo si regola in ~/.config/hypr/hyprlock.conf."))
    items.append(_item("Touch ID", "tid-sudo", "sudo", "impronta o password" if touchid_sudo_on() else "solo password", INFO))
    return items


# --- app Chromium/Electron (docs/gpu.md, scripts/fix-chromium-gpu.sh) --------------------------------

CHROMIUM_FIX = next((p for p in (LIBDIR + "/manager/fix-chromium-gpu",
                                  os.path.expanduser("~/.local/lib/macbookpro14-3/fix-chromium-gpu"))
                     if os.path.exists(p)), LIBDIR + "/manager/fix-chromium-gpu")
SHELLS = {"sh", "bash", "zsh", "fish", "dash", "python3", "pgrep", "grep"}


def chromium_gpu_processes():
    """[(app, accelerata, x11)] per ogni processo GPU di Chromium/Electron in esecuzione."""
    out = []
    for d in glob.glob("/proc/[0-9]*"):
        try:
            with open(d + "/cmdline", "rb") as f:
                cmd = f.read().replace(b"\0", b" ")   # Chromium riscrive argv come un'unica stringa
            app = os.path.basename(os.readlink(d + "/exe"))
        except OSError:
            continue
        if b" --type=gpu-process" not in cmd or app in SHELLS:
            continue
        out.append((app, b"--use-gl=disabled" not in cmd, b"--ozone-platform=x11" in cmd))
    return out


def chromium():
    procs = chromium_gpu_processes()
    if not procs:
        return []
    off = sorted({a for a, acc, _x in procs if not acc})
    on = sorted({a for a, acc, _x in procs if acc})
    if off:
        return [_item("App", "chromium", "App Chromium/Electron", "GPU spenta: " + ", ".join(off), WARN,
                      "Sotto Wayland il loro processo GPU crolla con i buffer tiled della Radeon. Dopo la correzione "
                      "(AMD_DEBUG=notiling solo per loro) chiudile e riaprile; Claude Desktop riattiva l'accelerazione "
                      "al prossimo avvio.",
                      "chromium-fix" if os.path.exists(CHROMIUM_FIX) else None)]
    return [_item("App", "chromium", "App Chromium/Electron", "GPU attiva: " + ", ".join(on), OK)]


COLLECTORS = [drivers, touchbar, touchid, sleep, wifi, battery, energy, chromium]


def collect():
    items = []
    for fn in COLLECTORS:
        try:
            items.extend(fn())
        except Exception as e:  # una voce rotta non deve fermare le altre
            items.append(_item("Errori", fn.__name__, fn.__name__, "lettura fallita: %s" % e, WARN))
    return items
