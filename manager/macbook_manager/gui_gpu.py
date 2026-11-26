"""Scheda "GPU" di MacBook Manager: stato delle due GPU, chi le usa, GPU dello schermo, profili della Radeon e GPU per
applicazione (gpu.py; le azioni di root passano dall'helper con gli id del gruppo "GPU" di actions.py)."""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QPushButton, QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from . import theme as T
from . import gpu as G
from .actions import BY_ID, available

CHOICES = [("default", "Predefinita"), ("radeon", "Radeon (prestazioni)"), ("intel", "Intel (risparmio)")]
KIND_NAME = {"intel": "Intel", "radeon": "Radeon"}


def _mib(b):
    return "%d MiB" % (b // 1048576) if b is not None else "-"


class _GpuBox(QGroupBox):
    ROWS = [("role", "Ruolo"), ("busy", "Utilizzo"), ("clock", "Frequenza"), ("power", "Potenza / temperatura"),
            ("vram", "Memoria video"), ("mode", "Gestione energia")]

    def __init__(self, title):
        super().__init__(title)
        g = QGridLayout(self)
        self.v = {}
        for i, (k, name) in enumerate(self.ROWS):
            lab = QLabel(name)
            lab.setStyleSheet("color: palette(placeholder-text);")
            val = QLabel("-")
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            g.addWidget(lab, i, 0)
            g.addWidget(val, i, 1)
            self.v[k] = (lab, val)
        g.setRowStretch(len(self.ROWS), 1)   # affiancato a un riquadro più alto: righe in cima, non sparse

    def set(self, k, text, visible=True):
        lab, val = self.v[k]
        val.setText(text)
        lab.setVisible(visible)
        val.setVisible(visible)


class GpuTab(QWidget):
    def __init__(self, log, run_action):
        super().__init__()
        self.log, self.run_action = log, run_action
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        lay = QVBoxLayout(body)
        scroll.setWidget(body)
        outer.addWidget(scroll)

        # stato delle GPU
        row = QHBoxLayout()
        self.boxes = {}
        for g in G.gpus():
            box = _GpuBox(g["name"])
            self.boxes[g["kind"]] = (g, box)
            row.addWidget(box)
        lay.addLayout(row)

        # chi usa le GPU
        ubox = QGroupBox("Chi sta usando le GPU (tempo di lavoro della GPU, aggiornato ogni 2 s)")
        ul = QVBoxLayout(ubox)
        self.usage = QTableWidget(0, 3)
        self.usage.setHorizontalHeaderLabels(["Programma", "GPU", "Uso"])
        h = self.usage.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.usage.verticalHeader().setVisible(False)
        self.usage.setEditTriggers(QTableWidget.NoEditTriggers)
        self.usage.setSelectionMode(QTableWidget.NoSelection)
        self.usage.setMinimumHeight(150)
        ul.addWidget(self.usage)
        note = QLabel("Conta solo i programmi del tuo utente (KWin, che compone lo schermo, non è leggibile). "
                      "Un programma può aprire entrambe le GPU: qui si vede su quale lavora davvero.")
        note.setWordWrap(True)
        note.setStyleSheet("color: palette(placeholder-text);")
        ul.addWidget(note)
        lay.addWidget(ubox)

        # GPU dello schermo
        dbox = QGroupBox("GPU dello schermo")
        dl = QVBoxLayout(dbox)
        self.disp = QLabel()
        self.disp.setWordWrap(True)
        self.disp.setTextFormat(Qt.RichText)
        dl.addWidget(self.disp)
        expl = QLabel(
            "<b>Intel</b>: circa 1,5-2 W in meno a riposo. I giochi e le app che disegnano sulla Radeon devono copiare "
            "ogni fotogramma alla Intel: di solito restano a 60 fps con tempi irregolari. "
            "<b>Radeon</b>: prestazioni piene nei giochi (anche oltre i 60 fps), consumo più alto. "
            "La Radeon resta comunque accesa in entrambi i casi. Il cambio vale dal prossimo avvio.")
        expl.setWordWrap(True)
        expl.setTextFormat(Qt.RichText)
        dl.addWidget(expl)
        self.action_buttons = {}
        dl.addLayout(self._buttons(["gpu-display-intel", "gpu-display-radeon"]))
        lay.addWidget(dbox)

        # Radeon
        rbox = QGroupBox("Radeon: gestione energia")
        rl = QVBoxLayout(rbox)
        rl.addLayout(self._buttons(["radeon-game", "radeon-auto", "radeon-powersave"]))
        rl.addLayout(self._buttons(["radeon-low", "radeon-high"]))
        rn = QLabel("Vale subito, fino al prossimo collegamento o scollegamento dell'alimentatore, quando tornano le regole "
                    "automatiche qui sotto. \"Clock al massimo\" scalda e consuma anche da ferma.")
        rn.setWordWrap(True)
        rn.setStyleSheet("color: palette(placeholder-text);")
        rl.addWidget(rn)
        lay.addWidget(rbox)

        # regole automatiche: Radeon a batteria e limite FPS
        from .gui_cpu import RulesBox
        self.rules = RulesBox("Regole automatiche: Radeon e limite FPS", "gpu", self.run_action)
        self.fps = QLabel()
        self.fps.setWordWrap(True)
        self.fps.setTextFormat(Qt.RichText)
        self.rules.layout().addWidget(self.fps, self.rules.layout().rowCount(), 0, 1, 3)
        lay.addWidget(self.rules)

        # GPU per applicazione
        abox = QGroupBox("GPU per applicazione")
        al = QVBoxLayout(abox)
        an = QLabel("Vale dal prossimo avvio dell'app dal menu (o dalla barra delle applicazioni). \"Predefinita\" "
                    "lascia scegliere all'app: di solito la GPU dello schermo, mentre molti giochi scelgono da soli la "
                    "Radeon. Per i giochi di Steam: opzioni di avvio <code>DRI_PRIME=1 %command%</code>.")
        an.setWordWrap(True)
        an.setTextFormat(Qt.RichText)
        al.addWidget(an)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Cerca un'applicazione…")
        self.filter.textChanged.connect(self._filter_apps)
        al.addWidget(self.filter)
        self.apps = QTableWidget(0, 2)
        self.apps.setHorizontalHeaderLabels(["Applicazione", "GPU"])
        h = self.apps.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.apps.verticalHeader().setVisible(False)
        self.apps.setEditTriggers(QTableWidget.NoEditTriggers)
        self.apps.setSelectionMode(QTableWidget.NoSelection)
        self.apps.setMinimumHeight(260)
        al.addWidget(self.apps)
        lay.addWidget(abox)
        lay.addStretch(1)

        self.prev = None
        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self._tick)
        self.loaded_apps = False

    # --- pulsanti delle azioni -------------------------------------------------------------------------------
    def _buttons(self, ids):
        row = QHBoxLayout()
        for aid in ids:
            a = BY_ID.get(aid)
            if not a:
                continue
            b = QPushButton(a["label"] + ("  🔒" if a["root"] else ""))
            b.setCheckable(True)
            b.setEnabled(available(a))
            b.setToolTip("Chiede la password di amministratore (polkit)" if a["root"] else "")
            b.clicked.connect(lambda _c=False, i=aid: self._run(i))
            self.action_buttons[aid] = b
            row.addWidget(b)
        row.addStretch(1)
        return row

    def _run(self, aid):
        self.run_action(aid)
        QTimer.singleShot(4000, self.sync)

    def _mark_active(self):
        for aid, b in self.action_buttons.items():
            a = BY_ID[aid]
            try:
                on = bool(a.get("active") and available(a) and a["active"]())
            except Exception:  # noqa: BLE001
                on = False
            b.setChecked(on)

    # --- aggiornamento -------------------------------------------------------------------------------------
    def showEvent(self, e):
        super().showEvent(e)
        self.sync()
        self.timer.start()

    def hideEvent(self, e):
        super().hideEvent(e)
        self.timer.stop()

    def sync(self):
        d = G.display_prefs()
        txt = "Adesso lo schermo è sulla <b>%s</b>; al prossimo avvio: <b>%s</b>." % (
            KIND_NAME.get(d["now"], d["now"]), KIND_NAME.get(d["next"], d["next"]))
        # Solo informativo: sul 14,3 la variabile basta anche senza OpenCore (26/11/2026, docs/gpu.md).
        txt += " Avvio da OpenCore: %s." % ("sì" if d["opencore"] else "no")
        self.disp.setText(txt)
        self._mark_active()
        self.rules.sync()
        from . import power as P
        f = P.fps_now()
        if not f["installed"]:
            ft = ("<span style='color:" + T.c("warn") + "'>Limite FPS non installato</span>: "
                  "<code>sudo scripts/install-power.sh</code>.")
        else:
            ft = "Limite adesso: <b>%s</b>." % ("nessuno" if not f["limit"] else "%d FPS" % f["limit"])
            if not f["session"]:
                ft += (" " + "<span style='color:" + T.c("warn") + "'>Questa sessione è partita prima dell'installazione: esci e rientra "
                       "perché le app carichino MangoHud.</span>")
            ft += (" Vale per giochi e app Vulkan (anche Proton/DXVK); le app OpenGL non sono limitate. "
                   "I giochi di Steam: attivo se Steam è partito da questa sessione.")
        self.fps.setText(ft)
        if not self.loaded_apps:
            self._load_apps()
        self._tick()

    def _tick(self):
        for kind, (g, box) in self.boxes.items():
            s = G.status(g)
            box.set("role", "schermo" + (" (GPU di avvio)" if g["boot_vga"] else "") if s["display"]
                    else "seconda GPU, senza schermo")
            box.set("busy", "%d %%" % s["busy"] if s["busy"] is not None else "-", kind == "radeon")
            box.set("clock", "%s / %s MHz" % (s["mhz"] or "-", s["max_mhz"] or "-"))
            box.set("power", "%s W, %s °C" % (s["watts"] if s["watts"] is not None else "-",
                                               s["temp"] if s["temp"] is not None else "-"), kind == "radeon")
            box.set("vram", "%s su %s" % (_mib(s["vram_used"]), _mib(s["vram_total"])), kind == "radeon")
            box.set("mode", "%s, profilo %s" % (s["level"], s["profile"]) if s["level"] else "-", kind == "radeon")
        cur = G.engine_sample()
        rows = G.engine_usage(self.prev, cur) if self.prev else []
        self.prev = cur
        kinds = {g["pci"]: g["kind"] for g, _b in self.boxes.values()}
        rows = [r for r in rows if r[3] >= 0.1][:12]
        self.usage.setRowCount(len(rows))
        for i, (pid, name, pci, pct) in enumerate(rows):
            it = QTableWidgetItem("%s  (pid %d)" % (name, pid))
            it.setToolTip(G.cmdline(pid)[:300])
            self.usage.setItem(i, 0, it)
            self.usage.setItem(i, 1, QTableWidgetItem(KIND_NAME.get(kinds.get(pci), pci)))
            p = QTableWidgetItem("%.1f %%" % pct)
            p.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.usage.setItem(i, 2, p)

    # --- app -----------------------------------------------------------------------------------------------
    def _load_apps(self):
        self.loaded_apps = True
        lst = G.apps()
        self.apps.setRowCount(len(lst))
        for i, a in enumerate(lst):
            it = QTableWidgetItem(QIcon.fromTheme(a["icon"] or "application-x-executable"), a["name"])
            it.setToolTip("%s\n%s" % (a["id"], a["path"]))
            self.apps.setItem(i, 0, it)
            combo = QComboBox()
            for cid, label in CHOICES:
                combo.addItem(label, cid)
            combo.setCurrentIndex(max(0, combo.findData(a["choice"])))
            combo.currentIndexChanged.connect(lambda _i, c=combo, did=a["id"], n=a["name"]: self._choose(did, n, c))
            self.apps.setCellWidget(i, 1, combo)
        self._filter_apps(self.filter.text())

    def _filter_apps(self, text):
        t = text.lower().strip()
        for i in range(self.apps.rowCount()):
            it = self.apps.item(i, 0)
            self.apps.setRowHidden(i, bool(t) and t not in it.text().lower() and t not in it.toolTip().lower())

    def _choose(self, desktop_id, name, combo):
        choice = combo.currentData()
        try:
            path = G.set_choice(desktop_id, choice)
        except (OSError, ValueError) as e:
            self.log("GPU: %s non modificata (%s)" % (name, e))
            return
        self.log("GPU: %s → %s (%s). Vale dal prossimo avvio dell'app." % (name, dict(CHOICES)[choice], path))
