"""Regole energetiche per alimentatore e batteria (/etc/macbookpro14-3/power.conf, applicate da power-source.sh e
dal servizio macbookpro14-3-cpu-limit), senza Qt. Le schede CPU e GPU le mostrano; ogni valore è un'azione root fissa
generata in actions.py ("pw-<lato>-<chiave>-<valore>"), quindi l'helper resta senza argomenti liberi."""
import glob
import json

from . import status

SIDES = [("AC", "Con l'alimentatore"), ("BATTERY", "A batteria")]
MAX_GHZ = 3.9

# chiave (senza AC_/BATTERY_), scheda, etichetta, spiegazione, [(valore, testo)], {lato: predefinito}, lati
SETTINGS = [
    ("NO_TURBO", "cpu", "Turbo", "Fino a 3,9 GHz con il turbo, 2,9 GHz senza. A riposo non cambia nulla; sotto carico "
     "il turbo consuma e scalda molto di più.",
     [("0", "acceso"), ("1", "spento")], {"AC": "0", "BATTERY": "1"}, ("AC", "BATTERY")),
    ("CPU_MAX_PCT", "cpu", "Frequenza massima", "Tetto della frequenza (intel_pstate max_perf_pct). Con il turbo "
     "spento il massimo resta comunque 2,9 GHz.",
     [(str(p), "%d %% (%.1f GHz)" % (p, MAX_GHZ * p / 100)) for p in (100, 90, 80, 70, 60, 50, 40)],
     {"AC": "100", "BATTERY": "100"}, ("AC", "BATTERY")),
    ("CPU_PROFILE", "cpu", "Profilo energetico", "Profilo di power-profiles-daemon (lo stesso del pannello di KDE): "
     "cambia quanto la CPU sale di frequenza sotto carico. \"Non cambiarlo\" lascia quello scelto in KDE.",
     [("keep", "non cambiarlo"), ("performance", "prestazioni massime"), ("balanced", "bilanciato"),
      ("power-saver", "risparmio energetico")], {"AC": "keep", "BATTERY": "keep"}, ("AC", "BATTERY")),
    ("CPU_POWER_W", "cpu", "Limite di potenza", "Potenza media massima della CPU (RAPL PL1). Il firmware la lascia a "
     "100 W: la CPU si ferma solo per il calore. 45 W è il valore di progetto dell'i7-7820HQ.",
     [("0", "firmware (100 W)"), ("45", "45 W"), ("35", "35 W"), ("25", "25 W"), ("15", "15 W")],
     {"AC": "0", "BATTERY": "0"}, ("AC", "BATTERY")),
    ("CPU_TEMP_LIMIT", "cpu", "Tetto di temperatura", "Sopra questa temperatura il servizio macbookpro14-3-cpu-limit "
     "abbassa la frequenza massima, e la rialza quando la CPU scende di 5 °C. Il firmware interviene comunque a 100 °C.",
     [("0", "nessuno"), ("95", "95 °C"), ("90", "90 °C"), ("85", "85 °C"), ("80", "80 °C"), ("75", "75 °C")],
     {"AC": "0", "BATTERY": "0"}, ("AC", "BATTERY")),
    ("FPS_LIMIT", "gpu", "Limite FPS", "Tetto ai fotogrammi al secondo dei giochi e delle app Vulkan (MangoHud, senza "
     "HUD). I giochi aperti si adeguano subito quando colleghi o stacchi l'alimentatore. Non vale per le app OpenGL.",
     [("0", "nessun limite"), ("120", "120 FPS"), ("90", "90 FPS"), ("60", "60 FPS"), ("30", "30 FPS")],
     {"AC": "0", "BATTERY": "60"}, ("AC", "BATTERY")),
    ("RADEON_MODE", "gpu", "Radeon", "Con l'alimentatore è sempre automatica con il profilo giochi. A batteria: clock al "
     "minimo (consumo più basso anche nei giochi, prestazioni ridotte), risparmio (POWER_SAVING) o automatica.",
     [("low", "clock al minimo"), ("save", "risparmio"), ("auto", "automatica")], {"BATTERY": "low"}, ("BATTERY",)),
]
BY_KEY = {s[0]: s for s in SETTINGS}


def action_id(side, key, value):
    return "pw-%s-%s-%s" % (side.lower(), key.lower().replace("_", "-"), value)


def current(side, key):
    """Valore salvato in power.conf (con i predefiniti di power-source.sh)."""
    conf = status.read_conf("power")
    v = conf.get("%s_%s" % (side, key))
    if v is None and key == "RADEON_MODE":  # compatibilità con BATTERY_RADEON_SAVE
        v = "save" if conf.get("BATTERY_RADEON_SAVE", "1") == "1" else "auto"
    return v if v is not None else BY_KEY[key][5].get(side)


def source():
    """AC o BATTERY, secondo l'alimentatore."""
    try:
        with open("/sys/class/power_supply/ADP1/online") as f:
            return "AC" if f.read().strip() == "1" else "BATTERY"
    except OSError:
        return "AC"


def cpu_state():
    """Stato pubblicato da cpu-limit.py (temperatura, tetto, watt del package) o {}."""
    try:
        with open("/run/macbookpro14-3/power/cpu.json") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def cpu_now():
    """Frequenze, temperatura, ventole, turbo, profilo, limiti attuali della CPU."""
    def rd(p, d=None):
        try:
            with open(p) as f:
                return f.read().strip()
        except OSError:
            return d
    freqs = []
    for p in glob.glob("/sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_cur_freq"):
        try:
            freqs.append(int(rd(p)) / 1e6)
        except (TypeError, ValueError):
            pass
    temp, fans = None, []
    for h in glob.glob("/sys/class/hwmon/hwmon*"):
        name = rd(h + "/name")
        if name == "coretemp":
            v = rd(h + "/temp1_input")
            temp = int(v) / 1000 if v else None
        elif name == "applesmc":
            fans = [int(rd(f, "0")) for f in sorted(glob.glob(h + "/fan[0-9]_input"))]
    thr = 0
    for p in glob.glob("/sys/devices/system/cpu/cpu[0-9]*/thermal_throttle/package_throttle_count"):
        try:
            thr = max(thr, int(rd(p)))
        except (TypeError, ValueError):
            pass
    pl1 = rd("/sys/class/powercap/intel-rapl:0/constraint_0_power_limit_uw")
    import subprocess
    try:
        prof = subprocess.run(["powerprofilesctl", "get"], capture_output=True, text=True, timeout=3).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        prof = ""
    return {
        "freq_avg": sum(freqs) / len(freqs) if freqs else None, "freq_max": max(freqs) if freqs else None,
        "temp": temp, "fans": fans, "throttle_count": thr,
        "no_turbo": rd("/sys/devices/system/cpu/intel_pstate/no_turbo") == "1",
        "max_pct": rd("/sys/devices/system/cpu/intel_pstate/max_perf_pct"),
        "epp": rd("/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference"),
        "profile": prof, "pl1_w": int(pl1) / 1e6 if pl1 else None,
    }


def fps_now():
    """Limite FPS scritto per MangoHud adesso (0 = nessuno) e se l'ambiente della sessione lo carica."""
    import os
    lim = None
    try:
        with open("/etc/macbookpro14-3/mangohud.conf") as f:
            for ln in f:
                if ln.startswith("fps_limit="):
                    lim = int(ln.split("=", 1)[1])
    except (OSError, ValueError):
        pass
    return {"limit": lim, "session": os.environ.get("MANGOHUD") == "1",
            "installed": os.path.exists("/etc/environment.d/90-macbookpro14-3-mangohud.conf")}
