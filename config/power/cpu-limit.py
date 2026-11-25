#!/usr/bin/python3 -I
"""Limite di temperatura della CPU del MacBookPro14,3 (servizio macbookpro14-3-cpu-limit, root).

Ogni 2 secondi legge /etc/macbookpro14-3/power.conf (AC_/BATTERY_CPU_TEMP_LIMIT e _CPU_MAX_PCT, secondo
l'alimentazione) e la temperatura del package (coretemp): sopra il limite abbassa intel_pstate/max_perf_pct (fino al
30 %), sotto il limite di 5 °C lo rialza piano fino al massimo scelto. Senza limite tiene il massimo scelto.
Pubblica lo stato per MacBook Manager in /run/macbookpro14-3/power/cpu.json (con i watt del package da RAPL, che
l'utente non può leggere).
"""
import glob
import json
import os
import time

CONF = "/etc/macbookpro14-3/power.conf"
PSTATE = "/sys/devices/system/cpu/intel_pstate/max_perf_pct"
RAPL = "/sys/class/powercap/intel-rapl:0/energy_uj"
OUT = "/run/macbookpro14-3/power/cpu.json"
FLOOR, STEP_UP, PERIOD = 30, 2, 2.0


def read(path, default=None):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return default


def conf():
    vals = {}
    for ln in (read(CONF, "") or "").splitlines():
        if "=" in ln and not ln.lstrip().startswith("#"):
            k, v = ln.split("=", 1)
            vals[k.strip()] = v.strip().strip('"')
    return vals


def num(v, default, lo, hi):
    try:
        v = int(v)
    except (TypeError, ValueError):
        return default
    return v if lo <= v <= hi else default


def package_temp():
    for h in glob.glob("/sys/class/hwmon/hwmon*"):
        if read(h + "/name") == "coretemp":
            v = read(h + "/temp1_input")
            return int(v) / 1000 if v else None
    return None


def log(msg):
    print(msg, flush=True)


def main():
    cap, last_written, throttling = 100, None, False
    e0, t0 = None, None
    while True:
        c = conf()
        side = "AC" if read("/sys/class/power_supply/ADP1/online") == "1" else "BATTERY"
        maxpct = num(c.get(side + "_CPU_MAX_PCT"), 100, FLOOR, 100)
        limit = num(c.get(side + "_CPU_TEMP_LIMIT"), 0, 60, 100)
        temp = package_temp()
        if limit and temp is not None:
            if temp >= limit:
                cap = max(FLOOR, cap - int(5 + (temp - limit) * 2))
            elif temp <= limit - 5:
                cap = min(100, cap + STEP_UP)
        else:
            cap = 100
        target = min(maxpct, cap)
        if target != last_written or read(PSTATE) != str(target):
            try:
                with open(PSTATE, "w") as f:
                    f.write(str(target))
                last_written = target
            except OSError as e:
                log("scrittura di max_perf_pct fallita: %s" % e)
        if limit and target < maxpct and not throttling:
            throttling = True
            log("CPU a %.0f °C, oltre il limite di %d °C: frequenza massima ridotta" % (temp, limit))
        elif throttling and target >= maxpct:
            throttling = False
            log("CPU sotto il limite di %d °C: frequenza massima ripristinata" % limit)
        # watt del package (RAPL)
        e, t, watts = read(RAPL), time.monotonic(), None
        if e is not None:
            e = int(e)
            if e0 is not None and e >= e0 and t > t0:
                watts = round((e - e0) / 1e6 / (t - t0), 1)
            e0, t0 = e, t
        state = {"ts": int(time.time()), "side": side, "temp": temp, "limit": limit, "max_pct": maxpct,
                 "cap": cap, "target": target, "throttling": throttling, "package_w": watts}
        try:
            os.makedirs(os.path.dirname(OUT), exist_ok=True)
            with open(OUT + ".tmp", "w") as f:
                json.dump(state, f)
            os.chmod(OUT + ".tmp", 0o644)
            os.replace(OUT + ".tmp", OUT)
        except OSError:
            pass
        time.sleep(PERIOD)


if __name__ == "__main__":
    main()
