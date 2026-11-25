"""Azioni rapide. Le azioni root le esegue SOLO macbook-manager-helper (via pkexec), che accetta questi id e
nient'altro: nessun argomento libero, nessuna shell. Le azioni utente girano direttamente.

Campi: id, group, label, root, steps (lista di argv, oppure ("conf", file, chiave, valore) per power.conf),
needs (file che deve esistere perché l'azione abbia senso), confirm (testo di conferma), long (lunga: mostra il log),
active (funzione: True se lo stato che l'azione imposta è già quello attuale; la GUI la mostra spuntata),
then ((id, domanda): dopo la riuscita la GUI chiede se eseguire anche quell'azione).
"""
import os

from . import LIBDIR, status

_pw = lambda key: status.read_conf("power").get(key) == "1"  # noqa: E731
_webcam = lambda: status.user_unit_active("macbookpro14-3-webcam.service")  # noqa: E731

TBMODE = "/usr/local/bin/touchbar-mode"
POWER_APPLY = [LIBDIR + "/power-source.sh"]
TIDPAM = "/usr/local/bin/touchid-pam"

ACTIONS = [
    # Touch Bar
    dict(id="touchbar-display", group="Touch Bar", label="Modalità display (grafica)", root=True,
         steps=[[TBMODE, "set", "display"]], active=lambda: status.touchbar_mode() == "display"
         and status.read_conf("touchbar").get("TOUCHBAR_MODE") == "display", needs=[TBMODE, LIBDIR + "/t1bridge/t1-touchbar-hw"]),
    dict(id="touchbar-keyboard", group="Touch Bar", label="Modalità tastiera (layout fissi)", root=True,
         steps=[[TBMODE, "set", "keyboard"]], needs=[TBMODE],
         active=lambda: status.read_conf("touchbar").get("TOUCHBAR_MODE", "keyboard") == "keyboard",
         then=("poweroff", "Modalità tastiera salvata. Il T1 riparte pulito solo con uno spegnimento completo: fino ad "
                           "allora resta la grafica. Spegnere ora? (Riaccendi dopo ~30 s.)")),
    dict(id="renderer-restart", group="Touch Bar", label="Riavvia il renderer", root=False,
         steps=[["systemctl", "--user", "restart", "macbookpro14-3-touchbar-renderer.service"]], needs=[TBMODE]),
    # Renderer della modalità display (touchbar-mode renderer): fnstrip/T1Bridge oppure tiny-dfr (install-tiny-dfr.sh).
    # Il renderer salvato è spuntato; la riga in Stato dice quale gira davvero.
    dict(id="renderer-t1bridge", group="Touch Bar", label="Renderer fnstrip / T1Bridge", root=True,
         steps=[[TBMODE, "renderer", "t1bridge"]], needs=[TBMODE, status.TDFR_BIN],
         active=lambda: status.read_conf("touchbar").get("TOUCHBAR_RENDERER", "t1bridge") == "t1bridge"),
    dict(id="renderer-tiny-dfr", group="Touch Bar", label="Renderer tiny-dfr", root=True,
         steps=[[TBMODE, "renderer", "tiny-dfr"]], needs=[TBMODE, status.TDFR_BIN],
         active=lambda: status.read_conf("touchbar").get("TOUCHBAR_RENDERER") == "tiny-dfr"
         and status.system_unit_active(status.TDFR_UNIT)),
    dict(id="webcam-on", group="Touch Bar", label="Webcam virtuale accesa", root=False,
         steps=[["/usr/local/bin/t1-webcam", "on"]], active=_webcam, needs=["/usr/local/bin/t1-webcam"]),
    dict(id="webcam-off", group="Touch Bar", label="Webcam virtuale spenta", root=False,
         steps=[["/usr/local/bin/t1-webcam", "off"]], active=lambda: not _webcam(), needs=["/usr/local/bin/t1-webcam"]),
    # Touch ID (scripts/install-touchid.sh, interruttori /usr/local/bin/touchid-pam)
    dict(id="touchid-kde", group="Touch ID", label="Gestisci impronte (Impostazioni di KDE)", root=False,
         steps=[["sh", "-c", "setsid -f systemsettings kcm_users >/dev/null 2>&1"]], needs=[TIDPAM, "/usr/bin/systemsettings"]),
    dict(id="touchid-verify", group="Touch ID", label="Prova impronta (appoggia il dito)", root=False,
         steps=[["fprintd-verify"]], needs=[TIDPAM, "/usr/bin/fprintd-verify"]),
    dict(id="touchid-list", group="Touch ID", label="Impronte registrate", root=False,
         steps=[["fprintd-list", "@USER@"]], needs=[TIDPAM, "/usr/bin/fprintd-list"]),
    dict(id="touchid-lock-on", group="Touch ID", label="Impronta nella schermata di blocco", root=True,
         steps=[[TIDPAM, "lockscreen", "on"]], needs=[TIDPAM], active=lambda: status.touchid_lockscreen_on(),
         confirm="Ogni sblocco con l'impronta consuma un'attivazione del relay: dopo ~68 in un avvio Touch ID si blocca "
                 "fino a uno spegnimento completo (T1Bridge issue #14). La password resta sempre valida. Attivare?"),
    dict(id="touchid-lock-off", group="Touch ID", label="Schermata di blocco solo con password", root=True,
         steps=[[TIDPAM, "lockscreen", "off"]], needs=[TIDPAM], active=lambda: not status.touchid_lockscreen_on()),
    dict(id="touchid-sudo-on", group="Touch ID", label="Impronta per sudo", root=True,
         steps=[[TIDPAM, "sudo", "on"]], needs=[TIDPAM], active=lambda: status.touchid_sudo_on()),
    dict(id="touchid-sudo-off", group="Touch ID", label="sudo solo con password", root=True,
         steps=[[TIDPAM, "sudo", "off"]], needs=[TIDPAM], active=lambda: not status.touchid_sudo_on()),
    # Sospensione
    dict(id="sleep-deep", group="Sospensione", label="S3 (deep): Mac freddo a coperchio chiuso", root=True,
         steps=[["systemctl", "enable", "--now", "macbookpro14-3-sleep-mode.service"]],
         active=lambda: status.sleep_mode() == "deep",
         needs=["/etc/systemd/system/macbookpro14-3-sleep-mode.service"]),
    dict(id="sleep-s2idle", group="Sospensione", label="s2idle (ripiego)", root=True,
         steps=[["systemctl", "disable", "--now", "macbookpro14-3-sleep-mode.service"]],
         active=lambda: status.sleep_mode() != "deep",
         needs=["/etc/systemd/system/macbookpro14-3-sleep-mode.service"],
         confirm="Con s2idle, a coperchio chiuso ventole e piattaforma restano accese e il Mac si sveglia da solo "
                 "ogni 30-40 minuti: non metterlo nello zaino. Continuare?"),
    # Energia
    dict(id="radeon-save-on", group="Energia", label="Radeon in risparmio a batteria: sì", root=True,
         steps=[("conf", "power", "BATTERY_RADEON_SAVE", "1"), POWER_APPLY], active=lambda: _pw("BATTERY_RADEON_SAVE"), needs=POWER_APPLY),
    dict(id="radeon-save-off", group="Energia", label="Radeon in risparmio a batteria: no", root=True,
         steps=[("conf", "power", "BATTERY_RADEON_SAVE", "0"), POWER_APPLY], active=lambda: not _pw("BATTERY_RADEON_SAVE"), needs=POWER_APPLY),
    dict(id="turbo-battery-off", group="Energia", label="Turbo CPU a batteria: spento", root=True,
         steps=[("conf", "power", "BATTERY_NO_TURBO", "1"), POWER_APPLY], active=lambda: _pw("BATTERY_NO_TURBO"), needs=POWER_APPLY),
    dict(id="turbo-battery-on", group="Energia", label="Turbo CPU a batteria: acceso", root=True,
         steps=[("conf", "power", "BATTERY_NO_TURBO", "0"), POWER_APPLY], active=lambda: not _pw("BATTERY_NO_TURBO"), needs=POWER_APPLY),
    # Rete e audio
    dict(id="wifi-reload", group="Rete e audio", label="Ricarica il driver Wi-Fi", root=True,
         steps=[["modprobe", "-r", "brcmfmac_wcc", "brcmfmac"], ["modprobe", "brcmfmac"]], needs=[]),
    dict(id="bt-headset", group="Rete e audio", label="Ripristina audio cuffie Bluetooth (chiamate)", root=True,
         steps=[["python3", "-I", LIBDIR + "/bt-sco-route.py", "hci0"]], needs=[LIBDIR + "/bt-sco-route.py"]),
    # Manutenzione
    dict(id="chromium-fix", group="Manutenzione", label="App Chromium/Electron: correzione GPU (Wayland)", root=False,
         steps=[[status.CHROMIUM_FIX]], needs=[status.CHROMIUM_FIX]),
    dict(id="poweroff", group="Manutenzione", label="Spegni il Mac (riavvia anche il T1)", root=False,
         steps=[["systemctl", "poweroff"]], needs=[],
         confirm="Il Mac si spegne: salva il lavoro. Riaccendilo dopo ~30 s (il T1 riparte pulito). Spegnere?"),
    dict(id="dkms-build", group="Manutenzione", label="Ricompila i driver per il kernel in uso (DKMS)", root=True,
         steps=[["dkms", "autoinstall", "-k", "@KERNEL@"]], needs=["/usr/bin/dkms"], long=True),
]

BY_ID = {a["id"]: a for a in ACTIONS}


def available(action):
    return all(os.path.exists(p) for p in action.get("needs", []))


def active_ids():
    """Id delle azioni il cui stato è già quello attuale (per spuntarle). Senza root."""
    out = set()
    for a in ACTIONS:
        try:
            if a.get("active") and available(a) and a["active"]():
                out.add(a["id"])
        except Exception:  # noqa: BLE001
            pass
    return out


def expand(argv):
    import pwd
    repl = {"@KERNEL@": os.uname().release, "@USER@": pwd.getpwuid(os.getuid()).pw_name}
    return [repl.get(a, a) for a in argv]
