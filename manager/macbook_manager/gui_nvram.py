"""Scheda "NVRAM" di MacBook Manager: suono di avvio, accensione aprendo il coperchio, GPU dello schermo, voce di avvio
(OpenCore o Linux, sempre o solo la prossima volta) ed elenco delle variabili Apple/OpenCore (nvram.py). Le scritture
passano dall'helper di root con gli id dei gruppi "NVRAM" e "GPU" di actions.py: nessun valore libero."""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QGroupBox, QHBoxLayout, QHeaderView, QLabel, QPushButton, QScrollArea, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from . import nvram as N
from .actions import BY_ID, available


class NvramTab(QWidget):
    def __init__(self, log, run_action):
        super().__init__()
        self.log, self.run_action = log, run_action
        self.action_buttons = {}
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        lay = QVBoxLayout(body)
        scroll.setWidget(body)
        outer.addWidget(scroll)

        intro = QLabel("Variabili che il firmware del Mac legge all'accensione. Valgono dal prossimo avvio; un reset "
                       "della NVRAM (⌥ ⌘ P R all'accensione) le riporta tutte ai valori di fabbrica.")
        intro.setWordWrap(True)
        lay.addWidget(intro)

        self.chime = self._group(lay, "Suono di avvio", ["nvram-chime-on", "nvram-chime-off"],
                                 "Variabile StartupMute. Se resta muto anche con \"attivo\", il volume salvato da macOS "
                                 "(SystemAudioVolume, sotto) è a zero [non verificato].")
        self.autoboot = self._group(lay, "Accensione col coperchio",
                                    ["nvram-autoboot-on", "nvram-autoboot-off"],
                                    "Il Mac si accende aprendo il coperchio o collegando l'alimentatore. Variabile "
                                    "AutoBoot (03 o assente = sì, 00 = no) [non verificato sul 14,3].")
        self.gpu = self._group(lay, "GPU dello schermo", ["gpu-display-intel", "gpu-display-radeon"],
                               "Variabile gpu-power-prefs, la stessa della scheda GPU: basta da sola, anche senza "
                               "OpenCore.")
        self.boot = self._group(lay, "Voce di avvio",
                                [["nvram-boot-default-opencore", "nvram-boot-default-linux"],
                                 ["nvram-boot-next-opencore", "nvram-boot-next-linux"]],
                                "Sempre: prima voce di BootOrder. Solo il prossimo avvio: BootNext. All'accensione "
                                "il tasto Option (⌥) mostra comunque tutte le voci.")
        self.boot_table = QTableWidget(0, 4)
        self.boot_table.setHorizontalHeaderLabels(["Voce", "Nome", "File", "Stato"])
        self._table_style(self.boot_table)
        self.boot.layout().addWidget(self.boot_table)

        allbox = QGroupBox("Tutte le variabili Apple, del gmux e di OpenCore (solo lettura)")
        al = QVBoxLayout(allbox)
        self.var_table = QTableWidget(0, 4)
        self.var_table.setHorizontalHeaderLabels(["Variabile", "Di", "Valore", "Significato"])
        self._table_style(self.var_table)
        al.addWidget(self.var_table)
        lay.addWidget(allbox)
        lay.addStretch(1)

    # --- costruzione ---------------------------------------------------------------------------------------
    def _table_style(self, t):
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QTableWidget.NoEditTriggers)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        t.horizontalHeader().setStretchLastSection(True)
        t.setMinimumHeight(140)

    def _group(self, lay, title, ids, note):
        box = QGroupBox(title)
        v = QVBoxLayout(box)
        state = QLabel("-")
        state.setTextInteractionFlags(Qt.TextSelectableByMouse)
        v.addWidget(state)
        # ids: una riga di azioni, oppure una lista di righe
        for line in (ids if ids and isinstance(ids[0], list) else [ids]):
            row = QHBoxLayout()
            for aid in line:
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
            v.addLayout(row)
        n = QLabel(note)
        n.setWordWrap(True)
        n.setStyleSheet("color: palette(placeholder-text);")
        v.addWidget(n)
        lay.addWidget(box)
        box.state = state
        return box

    def _run(self, aid):
        self.run_action(aid)
        QTimer.singleShot(4000, self.sync)

    # --- aggiornamento -------------------------------------------------------------------------------------
    def showEvent(self, e):
        super().showEvent(e)
        self.sync()

    def sync(self):
        c = N.chime()
        self.chime.state.setText("Adesso: <b>%s</b>" % ("muto" if c is False else "suona"
                                                       + (" (variabile assente: valore di fabbrica)" if c is None else "")))
        self.autoboot.state.setText("Adesso: <b>%s</b>" % ("sì" if N.autoboot() else "no"))
        from . import gpu as G
        d = G.display_prefs()
        name = {"intel": "Intel", "radeon": "Radeon"}
        self.gpu.state.setText("Adesso: <b>%s</b>; al prossimo avvio: <b>%s</b>. Avvio da OpenCore: %s." % (
            name.get(d["now"], d["now"]), name.get(d["next"], d["next"]), "sì" if N.opencore_booted() else "no"))

        b = N.boot_entries()
        first = b["order"][0] if b["order"] else None
        self.boot.state.setText("Ordine: <b>%s</b>%s" % (", ".join(b["order"]) or "-",
                                                         "; prossimo avvio: <b>%s</b>" % b["next"] if b["next"] else ""))
        self.boot_table.setRowCount(0)
        for num, label, path in b["entries"]:
            tags = []
            if num == b["current"]:
                tags.append("avviata ora")
            if num == first:
                tags.append("predefinita")
            if num == b["next"]:
                tags.append("prossimo avvio")
            r = self.boot_table.rowCount()
            self.boot_table.insertRow(r)
            for col, text in enumerate(["Boot" + num, label, path, ", ".join(tags)]):
                self.boot_table.setItem(r, col, QTableWidgetItem(text))

        self.var_table.setRowCount(0)
        for v in N.variables():
            r = self.var_table.rowCount()
            self.var_table.insertRow(r)
            value = v["value"] if len(v["value"]) <= 60 else v["value"][:60] + "…"
            meaning = (v["label"] + ": " + v["note"]) if v["label"] else ""
            for col, text in enumerate([v["name"], v["owner"], value, meaning]):
                it = QTableWidgetItem(text)
                it.setToolTip(v["raw"])
                self.var_table.setItem(r, col, it)

        for aid, btn in self.action_buttons.items():
            a = BY_ID[aid]
            try:
                btn.setChecked(bool(a.get("active") and available(a) and a["active"]()))
            except Exception:  # noqa: BLE001
                btn.setChecked(False)
