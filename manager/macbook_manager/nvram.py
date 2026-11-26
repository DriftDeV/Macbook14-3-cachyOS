"""Scheda NVRAM: lettura (senza root) delle variabili EFI utili del MacBookPro14,3 e delle voci di avvio.
Le scritture passano dalle azioni nvram-* (helper di root -> nvram-control.sh, comandi fissi) e, per la GPU dello
schermo, dalle azioni gpu-display-* (gpu-control.sh). Le variabili Apple in /sys/firmware/efi/efivars sono leggibili da
tutti (0644): 4 byte di attributi, poi il valore."""
import glob
import os
import re
import subprocess

VARS = "/sys/firmware/efi/efivars"
APPLE = "7c436110-ab2a-4bbb-a880-fe41995c9f82"
GMUX = "fa4ce28d-b62f-4c99-9cc3-6815686e30f9"
OC = "4d1fda02-38c7-4a6a-9cc6-4bcca8b30102"

# Variabili che la scheda spiega (nome, GUID, etichetta, decodifica, nota). Le altre si vedono nell'elenco completo.
KNOWN = {
    "StartupMute": ("Suono di avvio", lambda v: {"00": "suona", "01": "muto"}.get(v, v),
                    "00 = il Mac suona all'accensione, 01 = muto. Vale dalla prossima accensione."),
    "AutoBoot": ("Accensione aprendo il coperchio", lambda v: {"00": "no", "03": "sì"}.get(v, v),
                 "Assente o 03 = si accende aprendo il coperchio o collegando l'alimentatore; 00 = no [non verificato sul 14,3]."),
    "SystemAudioVolume": ("Volume del suono di avvio", lambda v: ("muto, " if v and int(v[:2], 16) & 0x80 else "")
                          + "livello %d" % (int(v[:2], 16) & 0x7f) if v else v,
                          "Scritto da macOS; il bit 0x80 indica muto. Solo lettura."),
    "gpu-power-prefs": ("GPU dello schermo", lambda v: {"01000000": "Intel", "00000000": "Radeon"}.get(v, v),
                        "La legge il firmware all'accensione e comanda il gmux. Si cambia dalla scheda GPU o qui sotto."),
    "csr-active-config": ("SIP di macOS", lambda v: v, "Solo per macOS (System Integrity Protection). Solo lettura."),
    "boot-args": ("Argomenti di avvio di macOS", lambda v: v, "Solo per macOS. Solo lettura."),
}


def _read(name, guid):
    try:
        with open("%s/%s-%s" % (VARS, name, guid), "rb") as f:
            raw = f.read()
    except OSError:
        return None
    return raw[4:]


def _text(raw):
    """Valore leggibile: testo se è testo stampabile, altrimenti esadecimale."""
    if raw and all(32 <= b < 127 or b in (0, 9, 10) for b in raw) and any(32 <= b < 127 for b in raw):
        return raw.rstrip(b"\0").decode("ascii", "replace")
    return raw.hex()


def variables():
    """Elenco delle variabili Apple, del gmux e di OpenCore: dict name, guid, owner, raw (hex), value, label, note."""
    out = []
    for path in sorted(glob.glob(VARS + "/*")):
        base = os.path.basename(path)
        m = re.match(r"^(.*)-([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$", base)
        if not m or m.group(2) not in (APPLE, GMUX, OC):
            continue
        name, guid = m.groups()
        raw = _read(name, guid) or b""
        owner = {APPLE: "Apple", GMUX: "Apple (gmux)", OC: "OpenCore/OCLP"}[guid]
        label, dec, note = KNOWN.get(name, ("", None, ""))
        try:
            value = dec(raw.hex() if name != "boot-args" else _text(raw)) if dec else _text(raw)
        except (ValueError, IndexError):
            value = raw.hex()
        out.append(dict(name=name, guid=guid, owner=owner, raw=raw.hex(), value=value, label=label, note=note))
    return out


def chime():
    """True = suona, False = muto, None = variabile assente (comportamento di fabbrica: suona)."""
    v = _read("StartupMute", APPLE)
    return None if v is None else v[:1] != b"\x01"


def autoboot():
    """True = si accende aprendo il coperchio (anche se la variabile manca), False = no."""
    v = _read("AutoBoot", APPLE)
    return True if v is None else v[:1] != b"\x00"


def boot_entries():
    """dict current, next, order (lista), entries [(num, label, path)] da efibootmgr (senza root)."""
    try:
        out = subprocess.run(["efibootmgr", "-v"], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        return {"current": None, "next": None, "order": [], "entries": []}
    res = {"current": None, "next": None, "order": [], "entries": []}
    for line in out.splitlines():
        if line.startswith("BootCurrent:"):
            res["current"] = line.split(":", 1)[1].strip()
        elif line.startswith("BootNext:"):
            res["next"] = line.split(":", 1)[1].strip()
        elif line.startswith("BootOrder:"):
            res["order"] = [x.strip() for x in line.split(":", 1)[1].split(",") if x.strip()]
        else:
            m = re.match(r"^Boot([0-9A-Fa-f]{4})\*?\s+(.*?)\t(.*)$", line)
            if m:
                path = m.group(3)
                f = re.search(r"\\?(EFI\\[^\s)]+\.efi)", path, re.I)
                res["entries"].append((m.group(1), m.group(2).strip(), f.group(1) if f else path[:60]))
    return res


def kind(label):
    """opencore, linux o "" per un'etichetta di voce di avvio (come nvram-control.sh)."""
    if "OpenCore" in label:
        return "opencore"
    if re.search(r"Limine|GRUB|CachyOS|Omarchy|Arch|Linux Boot Manager|rEFInd", label):
        return "linux"
    return ""


def opencore_booted():
    """OpenCore espone boot-path (variabile volatile) solo se è partito in questo avvio."""
    return bool(glob.glob(VARS + "/boot-path-" + OC))
