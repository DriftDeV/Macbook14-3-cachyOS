"""GPU del MacBookPro14,3 (Intel HD 630 + Radeon Pro 560) per la scheda GPU di MacBook Manager, senza Qt, senza root.

- Stato di ogni GPU: ruolo (schermo o no), utilizzo, frequenza, potenza e temperatura (Radeon), VRAM.
- Uso per processo: da /proc/<pid>/fdinfo (drm-engine-*: nanosecondi di lavoro per client DRM), quindi chi disegna
  davvero su quale GPU e quanto, non solo chi la apre (KWin e molte app aprono entrambe).
- GPU dello schermo: quella attuale e la scelta per il prossimo avvio (variabile EFI gpu-power-prefs; la cambia
  l'helper di root con gpu-control.sh).
- GPU per applicazione: nei .desktop (copia utente in ~/.local/share/applications per quelli di sistema) aggiunge
  "env MBM_GPU=<gpu> DRI_PRIME=... MESA_VK_DEVICE_SELECT=... MESA_VK_DEVICE_SELECT_FORCE_DEFAULT_DEVICE=1" davanti al
  programma: OpenGL (DRI_PRIME) e Vulkan (device-select di Mesa, che espone solo quella GPU) usano la GPU scelta, anche
  le app che scelgono da sole la "più potente" (wgpu, giochi). Se c'è già "env AMD_DEBUG=notiling" dell'Ottimizzazione,
  il nostro pezzo va subito dopo, così i due non si disturbano.
"""
import glob
import os
import re
import time

APPDIRS = ["/usr/share/applications", "/usr/local/share/applications"]
USER_APPS = os.path.expanduser("~/.local/share/applications")
EFIVAR = "/sys/firmware/efi/efivars/gpu-power-prefs-fa4ce28d-b62f-4c99-9cc3-6815686e30f9"
OC_BOOTPATH = glob.glob("/sys/firmware/efi/efivars/boot-path-4d1fda02-38c7-4a6a-9cc6-4bcca8b30102")
OPT_PREFIX = "env AMD_DEBUG=notiling "
OUR_RE = re.compile(r"env MBM_GPU=\S+(?: [A-Z_]+=\S+)* ")
KEY_COPY = "X-MacBookManager-GPU-Copy"


def _read(path, default=None):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return default


def _int(path):
    try:
        return int(_read(path))
    except (TypeError, ValueError):
        return None


# --- GPU presenti -----------------------------------------------------------------------------------------
def gpus():
    """Elenco delle GPU: dict con pci, ids, driver, card, render, name, kind (intel/radeon)."""
    out = []
    for dev in sorted(glob.glob("/sys/bus/pci/devices/*")):
        cls = _read(dev + "/class", "")
        if not cls.startswith("0x03"):
            continue
        drm = [os.path.basename(p) for p in glob.glob(dev + "/drm/*")]
        card = next((d for d in drm if d.startswith("card")), None)
        render = next((d for d in drm if d.startswith("renderD")), None)
        if not card:
            continue
        drv = os.path.basename(os.path.realpath(dev + "/driver"))
        ven, did = _read(dev + "/vendor", "")[2:], _read(dev + "/device", "")[2:]
        kind = {"i915": "intel", "amdgpu": "radeon"}.get(drv, drv)
        name = {"intel": "Intel HD Graphics 630", "radeon": "Radeon Pro 555/560"}.get(kind, drv)
        out.append({"pci": os.path.basename(dev), "dev": dev, "ids": "%s:%s" % (ven, did), "driver": drv,
                    "card": card, "render": render, "name": name, "kind": kind,
                    "boot_vga": _read(dev + "/boot_vga") == "1"})
    return out


def _hwmon(dev):
    for h in glob.glob(dev + "/hwmon/hwmon*"):
        return h
    return None


def status(g):
    """Stato attuale di una GPU (dict)."""
    s = {"display": False, "busy": None, "mhz": None, "max_mhz": None, "watts": None, "temp": None,
         "vram_used": None, "vram_total": None, "level": None, "profile": None, "runtime": None}
    for c in glob.glob("/sys/class/drm/%s-*" % g["card"]):
        if "eDP" in c and _read(c + "/enabled") == "enabled":
            s["display"] = True
    s["runtime"] = _read(g["dev"] + "/power/runtime_status")
    if g["kind"] == "radeon":
        d = g["dev"]
        s["busy"] = _int(d + "/gpu_busy_percent")
        lines = (_read(d + "/pp_dpm_sclk", "") or "").splitlines()
        for ln in lines:
            m = re.search(r"(\d+)Mhz", ln)
            if m and "*" in ln:
                s["mhz"] = int(m.group(1))
            if m:
                s["max_mhz"] = max(s["max_mhz"] or 0, int(m.group(1)))
        h = _hwmon(d)
        if h:
            w = _int(h + "/power1_average") or _int(h + "/power1_input")
            s["watts"] = round(w / 1e6, 1) if w else None
            t = _int(h + "/temp1_input")
            s["temp"] = t // 1000 if t else None
        u, t = _int(d + "/mem_info_vram_used"), _int(d + "/mem_info_vram_total")
        s["vram_used"], s["vram_total"] = u, t
        s["level"] = _read(d + "/power_dpm_force_performance_level")
        for ln in (_read(d + "/pp_power_profile_mode", "") or "").splitlines():
            if "*" in ln:
                s["profile"] = ln.split()[1].rstrip(":*")
    elif g["kind"] == "intel":
        c = "/sys/class/drm/" + g["card"]
        s["mhz"] = _int(c + "/gt_act_freq_mhz")
        s["max_mhz"] = _int(c + "/gt_max_freq_mhz")
    return s


# --- uso per processo (fdinfo) ----------------------------------------------------------------------------
def engine_sample():
    """{(pid, pci): (nome, ns totali)} sommando i motori di ogni client DRM (contato una volta per drm-client-id)."""
    out = {}
    for fdinfo in glob.glob("/proc/[0-9]*/fdinfo"):
        pid = fdinfo.split("/")[2]
        try:
            fds = os.listdir(fdinfo)
        except OSError:
            continue
        seen = set()
        for fd in fds:
            try:
                if not os.readlink("/proc/%s/fd/%s" % (pid, fd)).startswith("/dev/dri/"):
                    continue
                with open("%s/%s" % (fdinfo, fd)) as f:
                    txt = f.read()
            except OSError:
                continue
            pdev = re.search(r"^drm-pdev:\s*(\S+)", txt, re.M)
            cid = re.search(r"^drm-client-id:\s*(\d+)", txt, re.M)
            if not pdev or not cid or (pdev.group(1), cid.group(1)) in seen:
                continue
            seen.add((pdev.group(1), cid.group(1)))
            ns = sum(int(v) for v in re.findall(r"^drm-engine-[\w-]+:\s*(\d+) ns", txt, re.M))
            if not ns:
                continue
            key = (int(pid), pdev.group(1))
            if key not in out:
                out[key] = [_read("/proc/%s/comm" % pid, "?"), 0]
            out[key][1] += ns
    return {k: tuple(v) for k, v in out.items()}, time.monotonic()


def engine_usage(prev, cur):
    """[(pid, nome, pci, % del tempo della GPU)] fra due campioni di engine_sample(), dal più alto."""
    (p, t0), (c, t1) = prev, cur
    dt = (t1 - t0) * 1e9
    if dt <= 0:
        return []
    res = []
    for k, (name, ns) in c.items():
        if k in p:
            d = ns - p[k][1]
            if d > 0:
                res.append((k[0], name, k[1], min(100.0, 100 * d / dt)))
    return sorted(res, key=lambda x: -x[3])


def cmdline(pid):
    raw = _read("/proc/%d/cmdline" % pid, "") or ""
    return raw.replace("\0", " ").strip()


# --- GPU dello schermo ------------------------------------------------------------------------------------
def display_prefs():
    """{"now": intel|radeon|?, "next": intel|radeon|?, "opencore": bool}."""
    now = "?"
    for g in gpus():
        if status(g)["display"]:
            now = g["kind"]
    nxt = "?"
    try:
        with open(EFIVAR, "rb") as f:
            raw = f.read()
        if len(raw) >= 5:
            nxt = "intel" if raw[4] == 1 else "radeon"
    except OSError:
        pass
    return {"now": now, "next": nxt, "opencore": bool(OC_BOOTPATH)}


# --- GPU per applicazione ---------------------------------------------------------------------------------
def _parse(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            txt = f.read()
    except OSError:
        return None
    main = txt.split("\n[", 1)[0]  # solo [Desktop Entry]
    get = lambda k: (re.search(r"^%s=(.*)$" % re.escape(k), main, re.M) or [None, None])[1]  # noqa: E731
    return {"txt": txt, "name": get("Name"), "exec": get("Exec"), "icon": get("Icon"), "type": get("Type"),
            "nodisplay": (get("NoDisplay") or "").lower() == "true", "hidden": (get("Hidden") or "").lower() == "true"}


def choice_of(exec_line):
    m = re.search(r"env MBM_GPU=(\S+)", exec_line or "")
    return m.group(1) if m else "default"


def apps():
    """App visibili nel menu: [dict(id, name, icon, path, user, choice, optimized)] ordinate per nome."""
    found = {}
    for d in APPDIRS + [USER_APPS]:
        for path in glob.glob(os.path.join(d, "*.desktop")):
            found[os.path.basename(path)] = path  # quelle utente vincono (vengono dopo)
    out = []
    for did, path in found.items():
        info = _parse(path)
        if not info or info["type"] != "Application" or info["nodisplay"] or info["hidden"] or not info["exec"]:
            continue
        out.append({"id": did, "name": info["name"] or did, "icon": info["icon"], "path": path,
                    "user": path.startswith(USER_APPS), "choice": choice_of(info["exec"]),
                    "optimized": OPT_PREFIX.strip() in info["exec"]})
    return sorted(out, key=lambda a: a["name"].lower())


def _env_for(choice):
    g = {x["kind"]: x for x in gpus()}.get(choice)
    if not g:
        raise ValueError("GPU %s non trovata" % choice)
    prime = "pci-" + g["pci"].replace(":", "_").replace(".", "_")
    return ("env MBM_GPU=%s DRI_PRIME=%s MESA_VK_DEVICE_SELECT=%s MESA_VK_DEVICE_SELECT_FORCE_DEFAULT_DEVICE=1 "
            % (choice, prime, g["ids"]))


def _rewrite_exec(line, choice):
    """Riga Exec= con la nostra parte tolta e, se choice non è default, rimessa (dopo l'eventuale AMD_DEBUG)."""
    head, cmd = line.split("=", 1)
    cmd = OUR_RE.sub("", cmd)
    if choice != "default":
        ours = _env_for(choice)
        cmd = OPT_PREFIX + ours + cmd[len(OPT_PREFIX):] if cmd.startswith(OPT_PREFIX) else ours + cmd
    return head + "=" + cmd


def set_choice(desktop_id, choice):
    """choice: default | intel | radeon. Restituisce il percorso scritto (o rimosso)."""
    if choice not in ("default", "intel", "radeon"):
        raise ValueError(choice)
    if "/" in desktop_id or not desktop_id.endswith(".desktop"):
        raise ValueError(desktop_id)
    user = os.path.join(USER_APPS, desktop_id)
    src = user if os.path.exists(user) else next(
        (os.path.join(d, desktop_id) for d in APPDIRS if os.path.exists(os.path.join(d, desktop_id))), None)
    if not src:
        raise FileNotFoundError(desktop_id)
    with open(src, encoding="utf-8") as f:
        lines = f.read().split("\n")
    out = [_rewrite_exec(ln, choice) if re.match(r"^Exec=", ln) else ln for ln in lines]
    copy = src != user
    txt = "\n".join(out)
    if copy and choice != "default":
        # segna la copia come nostra, per toglierla quando si torna a "predefinita"
        txt = re.sub(r"^(\[Desktop Entry\]\n)", r"\1%s=true\n" % KEY_COPY, txt, count=1, flags=re.M)
    if not copy and choice == "default" and re.search(r"^%s=true$" % KEY_COPY, txt, re.M):
        txt = re.sub(r"^%s=true\n" % KEY_COPY, "", txt, flags=re.M)
        sysf = next((os.path.join(d, desktop_id) for d in APPDIRS if os.path.exists(os.path.join(d, desktop_id))), None)
        if sysf and _read(sysf) == txt.strip():  # copia nostra identica all'originale: la togliamo
            os.remove(user)
            _refresh()
            return user
    if copy and choice == "default":
        return src  # niente da togliere
    os.makedirs(USER_APPS, exist_ok=True)
    tmp = user + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(txt)
    os.replace(tmp, user)
    _refresh()
    return user


def _refresh():
    import shutil
    import subprocess
    if shutil.which("update-desktop-database"):
        subprocess.run(["update-desktop-database", "-q", USER_APPS], capture_output=True)
    if shutil.which("kbuildsycoca6"):
        subprocess.Popen(["kbuildsycoca6", "--noincremental"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
