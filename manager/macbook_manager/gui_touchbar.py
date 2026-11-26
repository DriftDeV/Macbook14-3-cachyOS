"""Scheda "Touch Bar": si adatta al renderer della modalità display (touchbar-mode renderer).

fnstrip / T1Bridge → editor di fnstrip (gui_fnstrip.py); tiny-dfr → editor di tiny-dfr (gui_tinydfr.py); OmaBar → editor
di OmaBar (gui_omabar.py). In alto si sceglie il renderer (azioni root renderer-t1bridge / renderer-tiny-dfr /
renderer-omabar, password via polkit).
"""
import os

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QStackedWidget, QVBoxLayout, QWidget

from . import status

RENDERERS = [("t1bridge", "fnstrip / T1Bridge"), ("tiny-dfr", "tiny-dfr (Asahi Linux)"),
             ("omabar", "OmaBar (tema di Omarchy)")]
# Renderer opzionali: binario che deve esserci e script che lo installa.
OPTIONAL = {"tiny-dfr": (status.TDFR_BIN, "scripts/install-tiny-dfr.sh"),
            "omabar": (status.OMABAR_BIN, "omarchy/install-omabar.sh")}


def renderer_now():
    """(renderer da configurare, testo di stato). In modalità display quello che gira, altrimenti quello salvato."""
    saved = status.read_conf("touchbar").get("TOUCHBAR_RENDERER", "t1bridge")
    if status.touchbar_mode() == "display":
        cur = status.touchbar_renderer()
        txt = "in uso" + ("" if cur == saved else " (salvato: %s)" % dict(RENDERERS).get(saved, saved))
        return cur, txt
    return saved, "salvato; la barra è in modalità tastiera"


class TouchBarTab(QWidget):
    def __init__(self, log, open_live, run_action):
        super().__init__()
        self.run_action = run_action
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        top.addWidget(QLabel("Renderer:"))
        self.combo = QComboBox()
        for rid, label in RENDERERS:
            self.combo.addItem(label, rid)
        top.addWidget(self.combo)
        self.state = QLabel()
        top.addWidget(self.state, 1)
        self.apply = QPushButton(QIcon.fromTheme("dialog-ok-apply"), "Usa questo renderer  🔒")
        self.apply.clicked.connect(self._apply)
        top.addWidget(self.apply)
        lay.addLayout(top)

        from .gui_fnstrip import FnstripEditor
        from .gui_omabar import OmaBarEditor
        from .gui_tinydfr import TinyDfrEditor
        self.fnstrip = FnstripEditor(log, open_live)
        self.tinydfr = TinyDfrEditor(log)
        self.omabar = OmaBarEditor(log)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.fnstrip)
        self.stack.addWidget(self.tinydfr)
        self.stack.addWidget(self.omabar)
        lay.addWidget(self.stack, 1)
        self.combo.currentIndexChanged.connect(self._combo_changed)
        self.sync()

    def sync(self):
        """Rilegge il renderer (all'apertura della scheda e dopo un'azione) e mostra l'editor giusto."""
        cur, txt = renderer_now()
        self.current = cur
        self.combo.blockSignals(True)
        self.combo.setCurrentIndex(max(0, self.combo.findData(cur)))
        self.combo.blockSignals(False)
        missing = []
        for i in range(self.combo.count()):
            rid = self.combo.itemData(i)
            if rid in OPTIONAL:
                there = os.path.exists(OPTIONAL[rid][0])
                self.combo.model().item(i).setEnabled(there)
                if not there:
                    missing.append("%s non installato (%s)" % (rid if rid != "omabar" else "OmaBar", OPTIONAL[rid][1]))
        self.state.setText(" · ".join([txt] + missing))
        self._show(cur)

    def _show(self, rid):
        ed = {"tiny-dfr": self.tinydfr, "omabar": self.omabar}.get(rid, self.fnstrip)
        self.stack.setCurrentWidget(ed)
        self.apply.setVisible(rid != self.current)
        ed._update_info()

    def _combo_changed(self, _i):
        # Si può guardare/preparare la configurazione dell'altro renderer prima di passare.
        self._show(self.combo.currentData())

    def _apply(self):
        self.run_action("renderer-" + self.combo.currentData())
